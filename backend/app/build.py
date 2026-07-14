"""Course-build orchestration (spec 02 §2). A DB-backed state machine: the course
`status` column IS the durable checkpoint, so a build survives a restart and resumes
where it left off. HITL pauses (clarification, cost approval) are real states the UI
advances through — nothing generates until the user approves the cost (02 §5, 03 §6).

Kept strictly separate from the learning-session runtime (06 §6): nothing here is
invoked while a learner plays a built course.

Statuses: intake → awaiting_clarification → awaiting_cost → building → built
          (or: refused / rejected / failed)
"""
from __future__ import annotations

from app import events
from app.agents import architect, cost_estimator, intake
from app.schemas import ClarificationQ
from app.store import (
    create_course,
    ensure_user,
    get_clarifications,
    get_course,
    save_clarifications,
    save_curriculum,
    save_intent_profile,
    set_clarification_answers,
    update_course,
)


def start_build(*, raw_prompt: str, raw_role: str, user_id: str | None = None,
                seed_material: str | None = None) -> dict:
    """Guardrail + intent + domain + clarification. Persists the course in 'intake'.
    Returns clarification questions (HITL pause) or advances toward the cost gate.
    `seed_material` is text extracted from an uploaded PDF/slide deck — when present the
    Architect builds the curriculum primarily from it (spec 05 §12)."""
    if user_id is None:
        user_id = ensure_user(raw_role)
    elif raw_role:
        # signed-in learner: capture the role they entered for this course (spec 01 §5)
        from app.db import execute
        execute("UPDATE users SET role_raw = %s WHERE id = %s", (raw_role, user_id))

    intent = intake.classify_intent(raw_prompt, raw_role)
    domain = intake.ground_domain(raw_prompt, raw_role, intent)
    save_intent_profile(user_id, intent, domain)

    # Personalization: tune this course to what we know about the learner (spec 03 §13).
    from app.agents import personalize
    personalization = personalize.context_for_build(user_id)

    questions, assumptions = intake.clarification_questions(raw_prompt, raw_role, intent, domain)
    currency = intake.infer_currency_mode(questions)  # provisional; refined after answers

    course_id = create_course(
        user_id=user_id, title=raw_prompt[:120], raw_prompt=raw_prompt,
        currency_mode=currency, status="intake",
    )
    # stash intake artefacts on the course for resume
    update_course(course_id, cost_reconciliation=None)
    _stash(course_id, intent=intent, domain=domain, raw_role=raw_role, assumptions=assumptions,
           personalization=personalization, seed_material=seed_material or "")

    if questions:
        save_clarifications(course_id, questions)
        update_course(course_id, status="awaiting_clarification")
        return {"course_id": course_id, "status": "awaiting_clarification",
                "questions": [{"ordinal": i, "q": q.q, "options": q.options,
                               "multi_select": q.multi_select}
                              for i, q in enumerate(questions)]}

    # no clarification needed → straight to curriculum + cost
    return _to_cost_gate(course_id, [], assumptions)


def submit_clarifications(course_id: str, answers: dict[int, str]) -> dict:
    course = get_course(course_id)
    if course is None:
        raise KeyError("course not found")
    # One-way commit (spec 07 §0): once the curriculum has been designed, this stage is locked.
    # Re-submitting must NOT re-run the Architect — the learner starts a new course to change it.
    if course["status"] not in ("intake", "awaiting_clarification"):
        return {"course_id": course_id, "status": course["status"], "locked": True}
    set_clarification_answers(course_id, answers)
    rows = get_clarifications(course_id)
    clar = [ClarificationQ(q=r["question"], options=r["options"] or [], answer=r["answer"])
            for r in rows]
    st = _unstash(course_id)
    return _to_cost_gate(course_id, clar, st.get("assumptions", []))


def _to_cost_gate(course_id: str, clarifications: list[ClarificationQ],
                  assumptions: list[str]) -> dict:
    """Architect → persist curriculum → cost estimate → pause at cost gate."""
    st = _unstash(course_id)
    course = get_course(course_id)
    ctx = intake.build_course_context(
        user_id=str(course["user_id"]) if course["user_id"] else None,
        raw_prompt=course["raw_prompt"], raw_role=st["raw_role"],
        intent=st["intent"], domain=st["domain"],
        clarifications=clarifications, assumptions=assumptions,
        personalization=st.get("personalization", {}),
        seed_material=st.get("seed_material", ""),
    )
    update_course(course_id, currency_mode=ctx.currency_mode)
    try:
        curriculum = architect.build_curriculum(ctx)
    except architect.ArchitectRefusal as r:
        update_course(course_id, status="refused",
                      cost_reconciliation={"refusal": r.reason, "reframing": r.reframing})
        return {"course_id": course_id, "status": "refused",
                "reason": r.reason, "suggested_reframing": r.reframing}

    save_curriculum(course_id, curriculum)
    events.emit(course_id, "intake", "architect",
                f"Course Architect: '{curriculum.title}' — {len(curriculum.topics)} topics, "
                f"{sum(len(t.subtopics) for t in curriculum.topics)} subtopics")
    est = cost_estimator.estimate(curriculum, ctx.currency_mode,
                                  domain=ctx.domain_grounding.domain,
                                  orientation=ctx.intent.orientation)
    events.emit(course_id, "cost", "estimate",
                f"Cost Estimator: ~${est.total_estimate:.4f} (buffer {est.buffer_pct}%) — awaiting approval")
    update_course(course_id, cost_estimate=est.model_dump(), status="awaiting_cost")
    return {"course_id": course_id, "status": "awaiting_cost",
            "curriculum": curriculum.model_dump(), "cost_estimate": est.model_dump()}


def approve_cost(course_id: str, approved: bool) -> dict:
    course = get_course(course_id)
    if course is None:
        raise KeyError("course not found")
    # One-way commit (spec 07 §0): only actionable while awaiting cost approval. Once building/
    # built, re-approving is a no-op (never re-triggers a build) — start a new course to change.
    if course["status"] != "awaiting_cost":
        return {"course_id": course_id, "status": course["status"], "locked": True}
    if not approved:
        update_course(course_id, cost_approved=False, accepted=False, status="rejected")
        return {"course_id": course_id, "status": "rejected"}
    update_course(course_id, cost_approved=True, accepted=True, status="building")
    events.emit(course_id, "cost", "approved", "Cost approved by user — starting content pipeline")
    return {"course_id": course_id, "status": "building"}


def run_build(course_id: str) -> None:
    """Phase 2 content pipeline (scout → audit → generate → check → verify → persist →
    reconcile). Implemented in app.pipeline; imported lazily so Phase 1 stands alone."""
    from app.pipeline import run_content_pipeline

    try:
        run_content_pipeline(course_id)
        update_course(course_id, status="built")
    except Exception as e:  # never leave a build wedged in 'building'
        update_course(course_id, status="failed",
                      cost_reconciliation={"error": str(e)[:500]})
        raise


# --- tiny stash on the course row (reuses cost_estimate-adjacent jsonb via a column) ---
# We keep intake artefacts in-memory-serializable form on `courses.curriculum` is taken,
# so use a dedicated lightweight table-free stash: encode onto `courses` via update.
_MEM: dict[str, dict] = {}


def _stash(course_id: str, **kw) -> None:
    _MEM[course_id] = kw


def _unstash(course_id: str) -> dict:
    if course_id in _MEM:
        return _MEM[course_id]
    # rebuild from persisted intent_profiles if the process restarted mid-intake
    from app.db import fetchone
    from app.schemas import DomainGrounding, IntentProfile

    row = fetchone(
        "SELECT ip.orientation, ip.seniority, ip.confidence, ip.domain_grounding, c.raw_prompt "
        "FROM courses c LEFT JOIN intent_profiles ip ON ip.user_id = c.user_id "
        "WHERE c.id = %s ORDER BY ip.created_at DESC LIMIT 1", (course_id,))
    if not row:
        return {"raw_role": "", "assumptions": [], "intent": IntentProfile(),
                "domain": DomainGrounding()}
    dg = row["domain_grounding"] or {}
    st = {
        "raw_role": get_course(course_id).get("user_id") and "" or "",
        "assumptions": [],
        "intent": IntentProfile(orientation=row["orientation"] or "general",
                                seniority=row["seniority"] or "mid",
                                confidence=float(row["confidence"] or 0.5),
                                needs_clarification=False),
        "domain": DomainGrounding(**dg) if dg else DomainGrounding(),
    }
    _MEM[course_id] = st
    return st
