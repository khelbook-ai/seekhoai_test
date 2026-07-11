"""Learning-session runtime (spec 02 §3, 04). Serves pre-generated interactions,
handles hints/content, MCQ→Q&A escalation, Q&A grading, scoring, weakness tracking,
and adaptive DL. Reads persisted content ONLY — never regenerates (token-free replay,
06 §6). Kept strictly separate from the build pipeline.
"""
from __future__ import annotations

from app.agents import adaptive, qa_grader
from app.db import execute, fetchall, fetchone
from app.scoring import mcq_score, qa_score

# server-authoritative hint tracking + pending escalation (spec 04 §8)
_HINTS: dict[tuple, set] = {}          # (session_id, interaction_id) -> {levels}
_PENDING: dict[str, dict] = {}         # session_id -> {qa_id, escalated_from}


def _ordered_interactions(course_id: str) -> list[dict]:
    return fetchall(
        """SELECT i.id, i.subtopic_id, i.type, i.dl, i.ordinal, i.question_md,
                  i.content_panel_md, i.diagram_ref, s.name subtopic, s.ordinal s_ord,
                  t.ordinal t_ord
           FROM interactions i JOIN subtopics s ON i.subtopic_id = s.id
           JOIN topics t ON s.topic_id = t.id
           WHERE t.course_id = %s ORDER BY t.ordinal, s.ordinal, i.ordinal""",
        (course_id,),
    )


def _answered_ids(session_id: str) -> set:
    rows = fetchall("SELECT interaction_id FROM responses WHERE session_id = %s", (session_id,))
    return {str(r["interaction_id"]) for r in rows}


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
    return {
        "id": str(it["id"]), "type": it["type"], "dl": it["dl"], "working_dl": wdl,
        "subtopic": it["subtopic"], "question_md": it["question_md"],
        "options": [{"label": o["label"], "text": o["text"]} for o in opts],
        "hints_available": hints_n, "has_content": bool(it["content_panel_md"]),
        "diagram_ref": str(it["diagram_ref"]) if it["diagram_ref"] else None,
        "base_score": it["dl"] * 2,
        "escalated_from": escalated_from,
    }


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
            return _public(it, course_id, session_id, escalated_from=pend["escalated_from"])
        _PENDING.pop(session_id, None)

    answered = _answered_ids(session_id)
    for it in _ordered_interactions(course_id):
        if str(it["id"]) not in answered:
            return _public(it, course_id, session_id)
    return None  # course complete


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


def submit_answer(session_id: str, interaction_id: str, *, selected_label: str | None = None,
                  answer_text: str | None = None) -> dict:
    course_id = _session_course(session_id)
    it = fetchone(
        "SELECT i.*, s.name subtopic FROM interactions i JOIN subtopics s ON i.subtopic_id=s.id "
        "WHERE i.id = %s", (interaction_id,))
    if it is None:
        raise KeyError("interaction not found")
    sess = fetchone("SELECT user_id FROM sessions WHERE id = %s", (session_id,))
    user_id = str(sess["user_id"]) if sess and sess["user_id"] else None
    hints = _hints_used(session_id, interaction_id)
    pend = _PENDING.get(session_id)
    escalated_from = pend["escalated_from"] if (pend and pend.get("qa_id") == interaction_id) else None

    result: dict
    if it["type"] == "mcq":
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
        # escalation: wrong MCQ → same-subtopic Q&A
        if not correct:
            qa = fetchone(
                "SELECT id FROM interactions WHERE subtopic_id = %s AND type='qa' "
                "AND id NOT IN (SELECT interaction_id FROM responses WHERE session_id=%s) LIMIT 1",
                (it["subtopic_id"], session_id))
            if qa:
                _PENDING[session_id] = {"qa_id": str(qa["id"]), "escalated_from": interaction_id}
                result["escalated"] = True
    else:  # qa
        grade = qa_grader.grade(dict(it), answer_text or "")
        score = qa_score(dl=it["dl"], hints_used=hints, band=grade["band"])
        execute(
            """INSERT INTO responses (session_id, interaction_id, user_answer, is_correct, band, dl,
                 hints_used, score_awarded, graded_by, grade_feedback_md, escalated_from)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'qa_grader',%s,%s)""",
            (session_id, interaction_id, answer_text, grade["correct"], grade["band"], it["dl"],
             hints, score, grade["feedback_md"], escalated_from),
        )
        result = {"correct": grade["correct"], "band": grade["band"],
                  "score_awarded": score, "rubric_hits": grade["rubric_hits"],
                  "rubric_misses": grade["rubric_misses"], "feedback_md": grade["feedback_md"],
                  "cached": grade.get("cached", False)}
        if adaptive.is_weakness(interaction_type="qa", correct=grade["correct"], band=grade["band"]):
            _flag_weakness(user_id, str(it["subtopic_id"]))
        if escalated_from:
            _PENDING.pop(session_id, None)

    running = fetchone("SELECT COALESCE(SUM(score_awarded),0) total FROM responses WHERE session_id=%s",
                       (session_id,))["total"]
    result["running_score"] = running
    result["next"] = current_interaction(session_id)
    return result


def dashboard(course_id: str, session_id: str | None = None) -> dict:
    """Progress + weaknesses (spec 04 §6, 07 §6)."""
    course = fetchone("SELECT user_id, title FROM courses WHERE id = %s", (course_id,))
    if course is None:
        raise KeyError("course not found")
    user_id = str(course["user_id"]) if course["user_id"] else None

    weaknesses = fetchall(
        """SELECT s.name subtopic, s.id subtopic_id, w.error_count, w.last_seen, t.name topic
           FROM weaknesses w JOIN subtopics s ON w.subtopic_id = s.id
           JOIN topics t ON s.topic_id = t.id
           WHERE (w.user_id = %s OR %s IS NULL) AND t.course_id = %s
           ORDER BY w.error_count DESC""", (user_id, user_id, course_id))

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
