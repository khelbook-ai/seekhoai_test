"""Course-build API (spec 07 §3-5). Drives the HITL build: create → clarify → cost
approval → (background) generation. The learning runtime is a separate router."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app import build, events
from app.db import fetchall
from app.guardrail import check
from app.store import get_clarifications, get_course, list_subtopics

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("")
def list_courses() -> dict:
    """All courses with their current stage — powers the left sidebar (spec 07 §0)."""
    rows = fetchall(
        "SELECT id, title, status, currency_mode, created_at FROM courses ORDER BY created_at DESC")
    return {"courses": [{"course_id": str(r["id"]), "title": r["title"], "status": r["status"],
                         "currency_mode": r["currency_mode"],
                         "created_at": r["created_at"].isoformat() if r["created_at"] else None}
                        for r in rows]}


@router.get("/{course_id}/events")
def build_events(course_id: str, after: int = 0) -> dict:
    """Live build log (spec 07 §5). Poll with the last-seen id in `after`."""
    return {"events": events.since(course_id, after_id=after)}


class CreateCourse(BaseModel):
    raw_prompt: str
    raw_role: str = ""
    tester_override: bool = False
    override_reason: str | None = None


@router.post("")
def create_course(req: CreateCourse) -> dict:
    g = check(req.raw_prompt, "course_prompt", tester_override=req.tester_override,
              override_reason=req.override_reason)
    if not g.allow:
        raise HTTPException(400, g.user_message or "prompt rejected by guardrail")
    if req.raw_role:
        gr = check(req.raw_role, "clarify", tester_override=req.tester_override,
                   override_reason=req.override_reason)
        role = gr.sanitized_text if gr.allow else req.raw_role
    else:
        role = ""
    return build.start_build(raw_prompt=g.sanitized_text, raw_role=role)


class ClarifyReq(BaseModel):
    answers: dict[str, str]  # {ordinal_str: answer}


@router.post("/{course_id}/clarify")
def clarify(course_id: str, req: ClarifyReq) -> dict:
    # guard each free-text answer (neutralised, never blocked at this entry point)
    clean: dict[int, str] = {}
    for k, v in req.answers.items():
        g = check(v, "clarify")
        clean[int(k)] = g.sanitized_text
    try:
        return build.submit_clarifications(course_id, clean)
    except KeyError:
        raise HTTPException(404, "course not found")


@router.get("/{course_id}")
def get_course_detail(course_id: str) -> dict:
    course = get_course(course_id)
    if course is None:
        raise HTTPException(404, "course not found")
    clar = get_clarifications(course_id)
    return {
        "course_id": course_id,
        "title": course["title"],
        "status": course["status"],
        "currency_mode": course["currency_mode"],
        "clarifications": [{"ordinal": c["ordinal"], "q": c["question"],
                            "options": c["options"] or [], "answer": c["answer"],
                            "multi_select": c.get("multi_select", False)} for c in clar],
        "curriculum": course["curriculum"],
        "cost_estimate": course["cost_estimate"],
        "cost_approved": course["cost_approved"],
        "cost_actual": float(course["cost_actual"]) if course["cost_actual"] is not None else None,
        "cost_delta_abs": float(course["cost_delta_abs"]) if course["cost_delta_abs"] is not None else None,
        "cost_delta_pct": float(course["cost_delta_pct"]) if course["cost_delta_pct"] is not None else None,
        "cost_reconciliation": course["cost_reconciliation"],
        "subtopics": list_subtopics(course_id),
    }


class CostApproval(BaseModel):
    approved: bool


@router.post("/{course_id}/cost-approval")
def cost_approval(course_id: str, req: CostApproval, bg: BackgroundTasks) -> dict:
    try:
        result = build.approve_cost(course_id, req.approved)
    except KeyError:
        raise HTTPException(404, "course not found")
    if result["status"] == "building":
        bg.add_task(build.run_build, course_id)  # Phase 2 pipeline runs in background
    return result


class RestartReq(BaseModel):
    mode: str = "resume"  # "resume" last session (default) or "fresh" session over same content
    user_id: str | None = None


@router.post("/{course_id}/restart")
def restart_with_content(course_id: str, req: RestartReq) -> dict:
    """Token-free replay (spec 06 §6): relaunch a learning session bound to the already
    built course. NEVER re-invokes the build pipeline."""
    from app import runtime
    from app.db import fetchone

    course = get_course(course_id)
    if course is None:
        raise HTTPException(404, "course not found")
    if req.mode == "resume":
        last = fetchone(
            "SELECT id FROM sessions WHERE course_id = %s ORDER BY started_at DESC LIMIT 1",
            (course_id,))
        if last:
            sid = str(last["id"])
            return {"session_id": sid, "course_id": course_id, "resumed": True,
                    "interaction": runtime.current_interaction(sid)}
    return runtime.create_session(course_id, req.user_id)
