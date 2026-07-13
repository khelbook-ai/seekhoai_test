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

QA_ANSWER_MAX = 300  # keep free-text answers short so grading stays token-cheap


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


class OpenSession(BaseModel):
    user_id: str | None = None


@router.post("/courses/{course_id}/open")
def open_session(course_id: str, req: OpenSession) -> dict:
    """Resume the learner's session for this course (or create one) — progress and score
    survive navigating away (spec 06 §6, 07 §2)."""
    try:
        return runtime.open_session(course_id, req.user_id)
    except KeyError:
        raise HTTPException(404, "course not found")


@router.get("/sessions/{session_id}/map")
def session_map(session_id: str) -> dict:
    try:
        return runtime.session_map(session_id)
    except KeyError:
        raise HTTPException(404, "session not found")


@router.get("/sessions/{session_id}/review/{interaction_id}")
def review(session_id: str, interaction_id: str) -> dict:
    try:
        return runtime.review_interaction(session_id, interaction_id)
    except KeyError:
        raise HTTPException(404, "interaction not found")


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
    response: dict | None = None   # order/blanks/dragdrop answer (spec 04 §1)


@router.post("/sessions/{session_id}/answer")
def submit_answer(session_id: str, req: AnswerReq) -> dict:
    answer_text = req.answer_text
    if answer_text:  # guard free-text before it reaches the grader (03 §0)
        g = check(answer_text, "qa_answer")
        # Cap length so grading tokens stay bounded (UI enforces 300; back it up here).
        answer_text = g.sanitized_text[:QA_ANSWER_MAX]
    try:
        return runtime.submit_answer(session_id, req.interaction_id,
                                     selected_label=req.selected_label, answer_text=answer_text,
                                     response=req.response)
    except KeyError:
        raise HTTPException(404, "interaction not found")


class ChatReq(BaseModel):
    query: str


CHAT_QUERY_MAX = 300  # keep the learner's question short to bound retrieval + answer tokens


@router.post("/sessions/{session_id}/chat")
def course_chat(session_id: str, req: ChatReq) -> dict:
    """Course-scoped RAG study assistant (spec 04 §12). Available once the learner has a session
    (i.e. started the questions). Searches ONLY this course's knowledge base and answers in
    ≤400 chars; the query is capped at 300 chars. Purely text."""
    sess = fetchone("SELECT course_id, user_id FROM sessions WHERE id = %s", (session_id,))
    if sess is None:
        raise HTTPException(404, "session not found")
    user_id = str(sess["user_id"]) if sess["user_id"] else None
    g = check(req.query, "chat", user_id=user_id)          # guard/sanitise free text (03 §0)
    query = g.sanitized_text[:CHAT_QUERY_MAX]
    if not query.strip():
        raise HTTPException(400, "empty question")
    from app import chat
    return chat.answer(str(sess["course_id"]), query, user_id=user_id, session_id=session_id)


@router.get("/users/{user_id}/chat")
def chat_history(user_id: str) -> dict:
    """The learner's whole course-assistant history across all their courses (spec 06 §10),
    so the panel can restore the conversation after a refresh."""
    from app import chat
    return {"messages": chat.history(user_id)}


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
