"""Learning-session API (spec 04, 07 §2/§6). Course-driven runtime: serve interactions,
hints, content; grade answers with MCQ→Q&A escalation; track weaknesses; dashboard.
Reads persisted content only — never regenerates (06 §6). Replaces the Phase 0 slice.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app import runtime
from app.blobstore import get_blobstore
from app.db import fetchone
from app.guardrail import check

router = APIRouter(prefix="/api", tags=["learning"])


class CreateSession(BaseModel):
    course_id: str
    user_id: str | None = None
    resume: bool = False  # resume last session over the same content (06 §6)


@router.post("/sessions")
def create_session(req: CreateSession) -> dict:
    if req.resume:
        last = fetchone(
            "SELECT id FROM sessions WHERE course_id = %s ORDER BY started_at DESC LIMIT 1",
            (req.course_id,))
        if last:
            sid = str(last["id"])
            return {"session_id": sid, "course_id": req.course_id, "resumed": True,
                    "interaction": runtime.current_interaction(sid)}
    try:
        return runtime.create_session(req.course_id, req.user_id)
    except KeyError:
        raise HTTPException(404, "course not found")


@router.get("/sessions/{session_id}/interaction")
def current_interaction(session_id: str) -> dict:
    try:
        it = runtime.current_interaction(session_id)
    except KeyError:
        raise HTTPException(404, "session not found")
    return {"interaction": it, "complete": it is None}


class HintReq(BaseModel):
    interaction_id: str
    level: int


@router.post("/sessions/{session_id}/hint")
def get_hint(session_id: str, req: HintReq) -> dict:
    try:
        return runtime.serve_hint(session_id, req.interaction_id, req.level)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError:
        raise HTTPException(404, "hint not found")


class ContentReq(BaseModel):
    interaction_id: str


@router.post("/sessions/{session_id}/content")
def get_content(session_id: str, req: ContentReq) -> dict:
    try:
        return runtime.serve_content(session_id, req.interaction_id)
    except KeyError:
        raise HTTPException(404, "interaction not found")


class AnswerReq(BaseModel):
    interaction_id: str
    selected_label: str | None = None
    answer_text: str | None = None


@router.post("/sessions/{session_id}/answer")
def submit_answer(session_id: str, req: AnswerReq) -> dict:
    answer_text = req.answer_text
    if answer_text:  # guard free-text before it reaches the grader (03 §0)
        g = check(answer_text, "qa_answer")
        answer_text = g.sanitized_text
    try:
        return runtime.submit_answer(session_id, req.interaction_id,
                                     selected_label=req.selected_label, answer_text=answer_text)
    except KeyError:
        raise HTTPException(404, "interaction not found")


@router.get("/courses/{course_id}/dashboard")
def dashboard(course_id: str, session_id: str | None = None) -> dict:
    try:
        return runtime.dashboard(course_id, session_id)
    except KeyError:
        raise HTTPException(404, "course not found")


@router.get("/blobs/{blob_id}")
def get_blob(blob_id: str) -> Response:
    got = get_blobstore().get(blob_id)
    if got is None:
        raise HTTPException(404, "blob not found")
    mime, data = got
    return Response(content=bytes(data), media_type=mime)
