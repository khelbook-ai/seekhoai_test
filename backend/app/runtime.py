"""Learning-session runtime (spec 02 §3, 04). Serves pre-generated interactions,
handles hints/content, MCQ→Q&A escalation, Q&A grading, scoring, weakness tracking,
and adaptive DL. Reads persisted content ONLY — never regenerates (token-free replay,
06 §6). Kept strictly separate from the build pipeline.
"""
from __future__ import annotations

import json

from app import interactions as interactions_mod
from app.agents import adaptive, qa_grader
from app.db import execute, fetchall, fetchone
from app.scoring import mcq_score, qa_score

# server-authoritative hint tracking + pending escalation (spec 04 §8)
_HINTS: dict[tuple, set] = {}          # (session_id, interaction_id) -> {levels}
_PENDING: dict[str, dict] = {}         # session_id -> {qa_id, escalated_from}


def _ordered_interactions(course_id: str) -> list[dict]:
    # MAIN sequence only: follow-up Q&A (role like 'followup_%') are served solely via the
    # MCQ→Q&A escalation path (spec 04 §4), never in the normal course flow.
    return fetchall(
        """SELECT i.id, i.subtopic_id, i.type, i.dl, i.ordinal, i.question_md,
                  i.content_panel_md, i.diagram_ref, i.walkthrough, i.payload, i.qa_rubric,
                  s.name subtopic, s.ordinal s_ord, t.name topic, t.ordinal t_ord
           FROM interactions i JOIN subtopics s ON i.subtopic_id = s.id
           JOIN topics t ON s.topic_id = t.id
           WHERE t.course_id = %s AND i.role = 'main'
           ORDER BY t.ordinal, s.ordinal, i.ordinal""",
        (course_id,),
    )


def _answered_ids(session_id: str) -> set:
    rows = fetchall("SELECT interaction_id FROM responses WHERE session_id = %s", (session_id,))
    return {str(r["interaction_id"]) for r in rows}


def _model_answer(it: dict) -> str | None:
    """The pre-generated reference answer for a Q&A (built into qa_rubric.model_answer). Served
    to the learner instantly on submit/review so the grader never has to write it (fast path)."""
    rub = it.get("qa_rubric")
    if isinstance(rub, str):
        try:
            rub = json.loads(rub)
        except (ValueError, TypeError):
            rub = None
    return (rub or {}).get("model_answer") if isinstance(rub, dict) else None


def _target_dl(session_id: str) -> int:
    """The learner's current working difficulty level, adapted across the whole session
    (spec 03 §12, 04 §5). Everyone starts at DL1; a streak of low-hint corrects promotes,
    a run of misses demotes. This is what routes the learner adaptively rather than linearly."""
    rows = fetchall(
        "SELECT is_correct correct, hints_used, band, dl FROM responses "
        "WHERE session_id = %s AND is_correct IS NOT NULL ORDER BY responded_at", (session_id,))
    if not rows:
        return 1
    return adaptive.working_dl(1, [dict(r) for r in rows])


def _pick_adaptive(items: list[dict], answered: set, session_id: str) -> dict | None:
    """Choose the next MAIN interaction adaptively (spec 04 §5): match the learner's working
    DL first, then favour a *different* topic than the one they just answered to keep the route
    engaging, then fall back to the natural course order. A subtopic's intro walkthrough is
    always served before that subtopic's first question."""
    unanswered = [it for it in items if str(it["id"]) not in answered]
    if not unanswered:
        return None
    target = _target_dl(session_id)
    last = fetchone(
        "SELECT i.subtopic_id FROM responses r JOIN interactions i ON r.interaction_id = i.id "
        "WHERE r.session_id = %s ORDER BY r.responded_at DESC LIMIT 1", (session_id,))
    last_sub = str(last["subtopic_id"]) if last else None
    last_topic = next((it["topic"] for it in items if str(it["subtopic_id"]) == last_sub), None)

    # Route on scored questions; walkthroughs ride along with their subtopic.
    pool = [it for it in unanswered if it["type"] != "walkthrough"] or unanswered

    def key(it: dict) -> tuple:
        return (abs(int(it["dl"]) - target),
                0 if it["topic"] != last_topic else 1,
                it["t_ord"], it["s_ord"], it["ordinal"])

    choice = min(pool, key=key)
    intro = [it for it in unanswered if it["type"] == "walkthrough"
             and str(it["subtopic_id"]) == str(choice["subtopic_id"])
             and it["ordinal"] < choice["ordinal"]]
    if intro:
        return min(intro, key=lambda it: it["ordinal"])
    return choice


def _public(it: dict, course_id: str, session_id: str, *, escalated_from: str | None = None) -> dict:
    opts = []
    if it["type"] == "mcq":
        opts = fetchall("SELECT label, text FROM mcq_options WHERE interaction_id = %s ORDER BY label",
                        (it["id"],))
    hints_n = fetchone("SELECT count(*) n FROM hints WHERE interaction_id = %s", (it["id"],))["n"]
    # adaptive working DL for display
    recent = fetchall(
        "SELECT is_correct correct, hints_used, band FROM responses WHERE session_id = %s "
        "ORDER BY responded_at DESC LIMIT 4", (session_id,))
    wdl = adaptive.working_dl(it["dl"], list(reversed([dict(r) for r in recent])))
    pub = {
        "id": str(it["id"]), "type": it["type"], "dl": it["dl"], "working_dl": wdl,
        "subtopic": it["subtopic"], "question_md": it["question_md"],
        "options": [{"label": o["label"], "text": o["text"]} for o in opts],
        "hints_available": hints_n, "has_content": bool(it["content_panel_md"]),
        "diagram_ref": str(it["diagram_ref"]) if it["diagram_ref"] else None,
        "base_score": it["dl"] * 2,
        "escalated_from": escalated_from,
    }
    if it["type"] == "qa":                # pre-generated reference answer (04 §11): the client
        pub["model_answer"] = _model_answer(it)  # holds it so it can be revealed instantly on submit
    if it["type"] == "walkthrough":       # read-only guided code tour (not scored)
        pub["walkthrough"] = it.get("walkthrough")
    if it["type"] in interactions_mod.RICH_TYPES:   # order/blanks/dragdrop — strip the answer
        pub["payload"] = interactions_mod.public_payload(str(it["id"]), it["type"], it.get("payload"))
    return pub


def create_session(course_id: str, user_id: str | None) -> dict:
    course = fetchone("SELECT user_id, status FROM courses WHERE id = %s", (course_id,))
    if course is None:
        raise KeyError("course not found")
    uid = user_id or (str(course["user_id"]) if course["user_id"] else None)
    row = execute("INSERT INTO sessions (user_id, course_id) VALUES (%s,%s) RETURNING id",
                  (uid, course_id))
    session_id = str(row["id"])
    return {"session_id": session_id, "course_id": course_id,
            "interaction": current_interaction(session_id)}


def _session_course(session_id: str) -> str:
    row = fetchone("SELECT course_id FROM sessions WHERE id = %s", (session_id,))
    if row is None:
        raise KeyError("session not found")
    return str(row["course_id"])


def current_interaction(session_id: str) -> dict | None:
    course_id = _session_course(session_id)
    # pending escalation takes priority
    pend = _PENDING.get(session_id)
    if pend:
        it = fetchone(
            "SELECT i.*, s.name subtopic FROM interactions i JOIN subtopics s ON i.subtopic_id=s.id "
            "WHERE i.id = %s", (pend["qa_id"],))
        if it and str(it["id"]) not in _answered_ids(session_id):
            pub = _public(it, course_id, session_id, escalated_from=pend["escalated_from"])
            pub["progress"] = _progress(course_id, session_id, it)
            return pub
        _PENDING.pop(session_id, None)

    answered = _answered_ids(session_id)
    it = _pick_adaptive(_ordered_interactions(course_id), answered, session_id)
    if it is None:
        return None  # course complete
    pub = _public(it, course_id, session_id)
    pub["progress"] = _progress(course_id, session_id, it)
    return pub


def _running(session_id: str) -> int:
    return fetchone("SELECT COALESCE(SUM(score_awarded),0) t FROM responses WHERE session_id=%s",
                    (session_id,))["t"]


def _progress(course_id: str, session_id: str, current_it: dict) -> dict:
    """In-course progress (spec 07 §2/§6): how far through, how many topics, where the
    learner is right now."""
    items = _ordered_interactions(course_id)
    total = len(items)
    answered = _answered_ids(session_id)
    done = sum(1 for it in items if str(it["id"]) in answered)
    topics: list[str] = []
    for it in items:
        if it["topic"] not in topics:
            topics.append(it["topic"])
    cur_sub = current_it.get("subtopic")
    cur_topic = next((it["topic"] for it in items if it["subtopic"] == cur_sub), topics[0] if topics else None)
    # Adaptive routing jumps across topics/DLs, so a linear index would move backwards. Report
    # position as "how many you've done + this one" — always forward.
    return {"answered": done, "total": total, "pct": round(100 * done / total) if total else 0,
            "position": min(done + 1, total) if total else 0, "topic_count": len(topics),
            "topics": topics, "current_topic": cur_topic, "current_subtopic": cur_sub,
            "running_score": _running(session_id)}


def open_session(course_id: str, user_id: str | None) -> dict:
    """Open the learner's session for this course — RESUME their most recent one so progress
    and score survive navigating away (spec 06 §6). Only creates a new session if none exists."""
    course = fetchone("SELECT user_id, status FROM courses WHERE id = %s", (course_id,))
    if course is None:
        raise KeyError("course not found")
    if user_id:
        last = fetchone("SELECT id FROM sessions WHERE course_id=%s AND user_id=%s "
                        "ORDER BY started_at DESC LIMIT 1", (course_id, user_id))
    else:
        last = fetchone("SELECT id FROM sessions WHERE course_id=%s ORDER BY started_at DESC LIMIT 1",
                        (course_id,))
    if last:
        sid = str(last["id"])
    else:
        uid = user_id or (str(course["user_id"]) if course["user_id"] else None)
        sid = str(execute("INSERT INTO sessions (user_id, course_id) VALUES (%s,%s) RETURNING id",
                          (uid, course_id))["id"])
    return {"session_id": sid, "course_id": course_id, "resumed": bool(last),
            "interaction": current_interaction(sid), "map": session_map(sid),
            "running_score": _running(sid)}


def session_map(session_id: str) -> dict:
    """Per-subtopic progress map for the Learn sub-tabs (spec 07 §2). Each main question is
    tagged correct / wrong / unanswered so completed ones get a green/red tick and can be
    reviewed read-only."""
    course_id = _session_course(session_id)
    resp = {str(r["interaction_id"]): r for r in fetchall(
        "SELECT interaction_id, is_correct, band, score_awarded FROM responses WHERE session_id=%s",
        (session_id,))}
    cur = current_interaction(session_id)
    cur_id = cur["id"] if cur else None
    groups: list[dict] = []
    index: dict[str, dict] = {}
    for it in _ordered_interactions(course_id):
        key = str(it["subtopic_id"])
        g = index.get(key)
        if g is None:
            g = {"subtopic_id": key, "subtopic": it["subtopic"], "topic": it["topic"], "items": []}
            index[key] = g
            groups.append(g)
        r = resp.get(str(it["id"]))
        if not r:
            status = "unanswered"
        elif it["type"] == "walkthrough":
            status = "reviewed"          # read-only, neutral tick (no green/red)
        else:
            status = "correct" if r["is_correct"] else "wrong"
        g["items"].append({"id": str(it["id"]), "type": it["type"], "dl": it["dl"],
                           "ordinal": it["ordinal"], "status": status,
                           "is_current": str(it["id"]) == cur_id, "followup": False})
    total = sum(len(g["items"]) for g in groups)
    done = sum(1 for g in groups for x in g["items"] if x["status"] != "unanswered")

    # Surface answered follow-up Q&As (escalation path, role != 'main'). They aren't part of
    # the main sequence, but the learner still answered them and must be able to go back and
    # review their answer + the correct one (requirement: Q&A history was invisible). Each is
    # slotted right after the MCQ that triggered it, within the same subtopic group.
    for f in fetchall(
        """SELECT i.id, i.subtopic_id, i.type, i.dl, i.ordinal, r.is_correct, r.escalated_from
           FROM responses r JOIN interactions i ON r.interaction_id = i.id
           JOIN subtopics s ON i.subtopic_id = s.id JOIN topics t ON s.topic_id = t.id
           WHERE r.session_id = %s AND t.course_id = %s AND i.role <> 'main'
           ORDER BY r.responded_at""", (session_id, course_id)):
        g = index.get(str(f["subtopic_id"]))
        if g is None:
            continue
        parent = str(f["escalated_from"]) if f["escalated_from"] else None
        item = {"id": str(f["id"]), "type": f["type"], "dl": f["dl"], "ordinal": f["ordinal"],
                "status": "correct" if f["is_correct"] else "wrong",
                "is_current": str(f["id"]) == cur_id, "followup": True, "parent_id": parent}
        pos = len(g["items"])
        if parent:
            pos = next((n + 1 for n, x in enumerate(g["items"]) if x["id"] == parent), pos)
        g["items"].insert(pos, item)

    return {"groups": groups, "current_id": cur_id, "answered": done, "total": total,
            "running_score": _running(session_id)}


def review_interaction(session_id: str, interaction_id: str) -> dict:
    """Read-only review of a completed interaction (spec 07 §2): the learner sees what they
    answered and the correct answer, but cannot reattempt."""
    it = fetchone("SELECT i.*, s.name subtopic FROM interactions i JOIN subtopics s "
                  "ON i.subtopic_id=s.id WHERE i.id = %s", (interaction_id,))
    if it is None:
        raise KeyError("interaction not found")
    r = fetchone("SELECT user_answer, is_correct, band, score_awarded, hints_used, grade_feedback_md "
                 "FROM responses WHERE session_id=%s AND interaction_id=%s ORDER BY responded_at DESC LIMIT 1",
                 (session_id, interaction_id))
    opts = fetchall("SELECT label, text, is_correct FROM mcq_options WHERE interaction_id=%s ORDER BY label",
                    (interaction_id,)) if it["type"] == "mcq" else []
    rich = it["type"] in interactions_mod.RICH_TYPES
    your_response = None
    if rich and r and r["user_answer"]:
        try:
            your_response = json.loads(r["user_answer"])
        except (ValueError, TypeError):
            your_response = None
    return {
        "id": str(it["id"]), "type": it["type"], "dl": it["dl"], "subtopic": it["subtopic"],
        "question_md": it["question_md"], "content_md": it["content_panel_md"],
        "walkthrough": it.get("walkthrough") if it["type"] == "walkthrough" else None,
        "payload": it.get("payload") if rich else None,   # full payload incl. correct answer
        "model_answer": _model_answer(it) if it["type"] == "qa" else None,
        "your_response": your_response,
        "diagram_ref": str(it["diagram_ref"]) if it["diagram_ref"] else None,
        "options": [{"label": o["label"], "text": o["text"], "is_correct": o["is_correct"]} for o in opts],
        "answer_key": it["answer_key"],
        "answered": r is not None,
        "your_answer": r["user_answer"] if r else None,
        "is_correct": r["is_correct"] if r else None,
        "band": r["band"] if r else None,
        "score_awarded": r["score_awarded"] if r else None,
        "hints_used": r["hints_used"] if r else 0,
        "feedback_md": r["grade_feedback_md"] if r else None,
    }


def serve_hint(session_id: str, interaction_id: str, level: int) -> dict:
    if level not in (1, 2, 3):
        raise ValueError("hint level must be 1, 2, or 3")
    row = fetchone("SELECT text_md FROM hints WHERE interaction_id = %s AND level = %s",
                   (interaction_id, level))
    if row is None:
        raise KeyError("hint not found")
    _HINTS.setdefault((session_id, interaction_id), set()).add(level)
    return {"level": level, "text_md": row["text_md"], "penalty": 1,
            "hints_used": len(_HINTS[(session_id, interaction_id)])}


def serve_content(session_id: str, interaction_id: str) -> dict:
    row = fetchone("SELECT content_panel_md FROM interactions WHERE id = %s", (interaction_id,))
    if row is None:
        raise KeyError("interaction not found")
    return {"content_md": row["content_panel_md"] or ""}


def _hints_used(session_id: str, interaction_id: str) -> int:
    return len(_HINTS.get((session_id, interaction_id), set()))


def _flag_weakness(user_id: str | None, subtopic_id: str) -> None:
    existing = fetchone("SELECT id, error_count FROM weaknesses WHERE user_id = %s AND subtopic_id = %s",
                        (user_id, subtopic_id))
    if existing:
        execute("UPDATE weaknesses SET error_count = error_count + 1, last_seen = now() WHERE id = %s",
                (existing["id"],))
    else:
        execute("INSERT INTO weaknesses (user_id, subtopic_id, error_count, last_seen) "
                "VALUES (%s,%s,1, now())", (user_id, subtopic_id))


def _session_intent(course_id: str) -> tuple[dict, dict]:
    row = fetchone(
        "SELECT ip.orientation, ip.seniority, ip.domain_grounding FROM courses c "
        "JOIN intent_profiles ip ON ip.user_id = c.user_id WHERE c.id = %s "
        "ORDER BY ip.created_at DESC LIMIT 1", (course_id,))
    if not row:
        return {"orientation": "general", "seniority": "mid"}, {"domain": "general", "must_ground": False}
    return ({"orientation": row["orientation"], "seniority": row["seniority"]},
            row["domain_grounding"] or {"domain": "general", "must_ground": False})


def _persist_probe(subtopic_id: str, item: dict, role: str) -> str:
    """Persist a runtime-generated follow-up Q&A (spec 04 §4). Runtime-only writer — kept
    out of the build pipeline; no diagrams, no build checkers."""
    import json

    gen = item.get("_gen", {})
    ordinal = fetchone("SELECT COALESCE(MAX(ordinal),0)+1 n FROM interactions WHERE subtopic_id=%s",
                       (subtopic_id,))["n"]
    row = execute(
        """INSERT INTO interactions
             (subtopic_id, type, role, dl, ordinal, question_md, content_panel_md, qa_rubric,
              gen_model, gen_latency_ms, gen_tokens_in, gen_tokens_out)
           VALUES (%s,'qa',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (subtopic_id, role, item.get("_dl", 1), ordinal, item.get("question_md"),
         item.get("content_panel_md"),
         json.dumps(item.get("qa_rubric")) if item.get("qa_rubric") else None,
         gen.get("model"), gen.get("latency_ms"), gen.get("tin"), gen.get("tout")),
    )
    iid = str(row["id"])
    for lvl, htext in enumerate(item.get("hints", [])[:3], start=1):
        execute("INSERT INTO hints (interaction_id, level, text_md) VALUES (%s,%s,%s)",
                (iid, lvl, htext))
    return iid


def _start_followup(session_id: str, mcq: dict, course_id: str) -> bool:
    """After a wrong MCQ, queue the subtopic's pre-generated seed follow-up. If it's already
    been used this session, generate a root-cause probe from the reserve instead."""
    seed = fetchone(
        "SELECT id FROM interactions WHERE subtopic_id = %s AND role = 'followup_seed' "
        "AND id NOT IN (SELECT interaction_id FROM responses WHERE session_id=%s) LIMIT 1",
        (mcq["subtopic_id"], session_id))
    base = {"escalated_from": str(mcq["id"]), "subtopic_id": str(mcq["subtopic_id"]),
            "base_dl": mcq["dl"], "probe_round": 0}
    if seed:
        _PENDING[session_id] = {**base, "qa_id": str(seed["id"])}
        return True
    # seed already used → jump straight to a generated probe
    return _next_probe(session_id, mcq, base, course_id)


def _next_probe(session_id: str, it: dict, pend: dict, course_id: str) -> bool:
    """Generate the next root-cause probe Q&A from the subtopic reserve (no scraping).
    Returns False when probes are exhausted so the runtime returns to the main sequence."""
    from app.agents.generators import followup
    from app.config import get_settings

    nxt = int(pend.get("probe_round", 0)) + 1
    if nxt > int(get_settings().section("followup").get("max_probe_rounds", 3)):
        return False
    subtopic_id = pend["subtopic_id"]
    row = fetchone("SELECT s.name, s.description, s.reserve FROM subtopics s WHERE s.id = %s",
                   (subtopic_id,))
    reserve = (row and row["reserve"]) or {}
    intent, domain = _session_intent(course_id)
    st_ctx = {"name": row["name"] if row else "", "description": row["description"] if row else "",
              "domain_grounding": domain}
    try:
        item = followup.generate_probe_followup(st_ctx, reserve, intent, int(pend.get("base_dl", 2)),
                                                nxt, course_id=None)
    except Exception:
        return False
    qa_id = _persist_probe(subtopic_id, item, "followup_probe")
    _PENDING[session_id] = {**pend, "qa_id": qa_id, "probe_round": nxt}
    return True


def submit_answer(session_id: str, interaction_id: str, *, selected_label: str | None = None,
                  answer_text: str | None = None, response: dict | None = None) -> dict:
    course_id = _session_course(session_id)
    it = fetchone(
        "SELECT i.*, s.name subtopic FROM interactions i JOIN subtopics s ON i.subtopic_id=s.id "
        "WHERE i.id = %s", (interaction_id,))
    if it is None:
        raise KeyError("interaction not found")
    # Prevent reattempting an already-answered question (spec 07 §2): return current state,
    # never re-score.
    if fetchone("SELECT 1 FROM responses WHERE session_id=%s AND interaction_id=%s LIMIT 1",
                (session_id, interaction_id)) is not None:
        return {"already_answered": True, "running_score": _running(session_id),
                "next": current_interaction(session_id)}
    sess = fetchone("SELECT user_id FROM sessions WHERE id = %s", (session_id,))
    user_id = str(sess["user_id"]) if sess and sess["user_id"] else None
    hints = _hints_used(session_id, interaction_id)
    pend = _PENDING.get(session_id)
    escalated_from = pend["escalated_from"] if (pend and pend.get("qa_id") == interaction_id) else None

    result: dict
    if it["type"] == "walkthrough":
        # read-only content: mark reviewed (non-scored) and advance to the paired MCQ
        execute(
            """INSERT INTO responses (session_id, interaction_id, user_answer, is_correct, dl,
                 hints_used, score_awarded, graded_by)
               VALUES (%s,%s,'reviewed',NULL,%s,0,0,'engine')""",
            (session_id, interaction_id, it["dl"]))
        result = {"reviewed": True, "score_awarded": 0}
    elif it["type"] in interactions_mod.RICH_TYPES:
        # order / blanks / dragdrop — graded deterministically, scored + escalated like an MCQ
        correct = interactions_mod.grade(it["type"], it.get("payload"), response or {})
        score = mcq_score(dl=it["dl"], hints_used=hints, correct=correct)
        execute(
            """INSERT INTO responses (session_id, interaction_id, user_answer, is_correct, dl,
                 hints_used, score_awarded, graded_by, escalated_from)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'engine',%s)""",
            (session_id, interaction_id, json.dumps(response or {}), correct, it["dl"], hints, score,
             escalated_from),
        )
        result = {"correct": correct, "score_awarded": score,
                  "solution": it.get("payload")}   # reveal the correct answer after submit
        if adaptive.is_weakness(interaction_type=it["type"], correct=correct, band=None):
            _flag_weakness(user_id, str(it["subtopic_id"]))
        if not correct and _start_followup(session_id, it, course_id):
            result["escalated"] = True
    elif it["type"] == "mcq":
        correct = (selected_label or "").strip().upper() == (it["answer_key"] or "").strip().upper()
        score = mcq_score(dl=it["dl"], hints_used=hints, correct=correct)
        execute(
            """INSERT INTO responses (session_id, interaction_id, user_answer, is_correct, dl,
                 hints_used, score_awarded, graded_by, escalated_from)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'engine',%s)""",
            (session_id, interaction_id, selected_label, correct, it["dl"], hints, score,
             escalated_from),
        )
        result = {"correct": correct, "correct_label": it["answer_key"], "score_awarded": score}
        if adaptive.is_weakness(interaction_type="mcq", correct=correct, band=None):
            _flag_weakness(user_id, str(it["subtopic_id"]))
        # escalation (spec 04 §4): wrong MCQ → pre-generated seed follow-up Q&A on the
        # same subtopic. If the seed was already used this session, generate a root-cause
        # probe from the reserve straight away.
        if not correct:
            if _start_followup(session_id, it, course_id):
                result["escalated"] = True
    else:  # qa
        grade = qa_grader.grade(dict(it), answer_text or "")
        score = qa_score(dl=it["dl"], hints_used=hints, band=grade["band"])
        this_round = pend.get("probe_round", 0) if (pend and pend.get("qa_id") == interaction_id) else 0
        execute(
            """INSERT INTO responses (session_id, interaction_id, user_answer, is_correct, band, dl,
                 hints_used, score_awarded, graded_by, grade_feedback_md, escalated_from, probe_round)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'qa_grader',%s,%s,%s)""",
            (session_id, interaction_id, answer_text, grade["correct"], grade["band"], it["dl"],
             hints, score, grade["feedback_md"], escalated_from, this_round),
        )
        result = {"correct": grade["correct"], "band": grade["band"],
                  "score_awarded": score, "rubric_hits": grade["rubric_hits"],
                  "rubric_misses": grade["rubric_misses"], "feedback_md": grade["feedback_md"],
                  "model_answer": _model_answer(it),  # pre-generated; shown instantly
                  "cached": grade.get("cached", False)}
        if adaptive.is_weakness(interaction_type="qa", correct=grade["correct"], band=grade["band"]):
            _flag_weakness(user_id, str(it["subtopic_id"]))
        # Root-cause follow-up loop (spec 04 §4): if this was a follow-up and the learner
        # is still not fully correct, generate the next root-cause probe from the reserve
        # (no scraping). On a full answer — or when probes are exhausted — return to the
        # main sequence (next MCQ).
        if pend and pend.get("qa_id") == interaction_id:
            if grade["band"] == "full":
                _PENDING.pop(session_id, None)
            elif not _next_probe(session_id, it, pend, course_id):
                _PENDING.pop(session_id, None)
            else:
                result["escalated"] = True
                result["followup"] = True

    result["running_score"] = _running(session_id)
    result["next"] = current_interaction(session_id)
    # On course completion, refresh the learner's cross-course profile from this session so the
    # NEXT course is better personalized (spec 03 §13).
    if result["next"] is None and user_id:
        try:
            from app.agents import personalize
            personalize.refresh_profile(user_id)
        except Exception:
            pass
    return result


def dashboard(course_id: str, session_id: str | None = None) -> dict:
    """Progress + weaknesses (spec 04 §6, 07 §6)."""
    course = fetchone("SELECT user_id, title FROM courses WHERE id = %s", (course_id,))
    if course is None:
        raise KeyError("course not found")
    user_id = str(course["user_id"]) if course["user_id"] else None

    # Scope weaknesses to this user when known; otherwise show the course's weaknesses.
    # (A NULL bound param inside `%s IS NULL` is an indeterminate type in Postgres and 500s —
    # build the filter in Python instead of relying on a nullable placeholder.)
    _wsql = ("""SELECT s.name subtopic, s.id subtopic_id, w.error_count, w.last_seen, t.name topic
                FROM weaknesses w JOIN subtopics s ON w.subtopic_id = s.id
                JOIN topics t ON s.topic_id = t.id WHERE t.course_id = %s{user}
                ORDER BY w.error_count DESC""")
    if user_id:
        weaknesses = fetchall(_wsql.format(user=" AND w.user_id = %s"), (course_id, user_id))
    else:
        weaknesses = fetchall(_wsql.format(user=""), (course_id,))

    # per-subtopic accuracy across this course's sessions
    acc = fetchall(
        """SELECT s.name subtopic, t.name topic,
                  count(*) attempts, sum(CASE WHEN r.is_correct THEN 1 ELSE 0 END) correct
           FROM responses r JOIN interactions i ON r.interaction_id = i.id
           JOIN subtopics s ON i.subtopic_id = s.id JOIN topics t ON s.topic_id = t.id
           WHERE t.course_id = %s GROUP BY s.name, t.name ORDER BY t.name""", (course_id,))

    score_series = []
    if session_id:
        rows = fetchall(
            "SELECT score_awarded, responded_at FROM responses WHERE session_id=%s ORDER BY responded_at",
            (session_id,))
        total = 0
        for r in rows:
            total += r["score_awarded"] or 0
            score_series.append(total)

    total_score = fetchone(
        "SELECT COALESCE(SUM(score_awarded),0) t FROM responses r JOIN interactions i ON r.interaction_id=i.id "
        "JOIN subtopics s ON i.subtopic_id=s.id JOIN topics tp ON s.topic_id=tp.id WHERE tp.course_id=%s",
        (course_id,))["t"]

    return {
        "course_id": course_id, "title": course["title"], "total_score": total_score,
        "weaknesses": [{"subtopic": w["subtopic"], "topic": w["topic"],
                        "error_count": w["error_count"],
                        "last_seen": w["last_seen"].isoformat() if w["last_seen"] else None}
                       for w in weaknesses],
        "accuracy": [{"subtopic": a["subtopic"], "topic": a["topic"],
                      "attempts": a["attempts"], "correct": a["correct"],
                      "pct": round(100 * a["correct"] / a["attempts"]) if a["attempts"] else 0}
                     for a in acc],
        "score_series": score_series,
    }
