"""Feedback API (spec 04 §7, 06 §2, 07). Content feedback (per interaction, mirrored to
the .md tree) and application feedback (page-scoped). Image upload + text-linking is
added in Phase 4 via the multipart endpoints below."""
from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.db import execute, fetchone
from app.feedback import save_application_feedback, save_content_feedback
from app.guardrail import check

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


def _interaction_context(interaction_id: str) -> dict:
    row = fetchone(
        """SELECT i.type, i.dl, s.name subtopic, c.title course, c.id course_id
           FROM interactions i JOIN subtopics s ON i.subtopic_id = s.id
           JOIN topics t ON s.topic_id = t.id JOIN courses c ON t.course_id = c.id
           WHERE i.id = %s""", (interaction_id,))
    if row is None:
        raise HTTPException(404, "interaction not found")
    return row


class ContentFeedbackReq(BaseModel):
    interaction_id: str
    feedback_md: str
    user_id: str | None = None
    image_links: list[dict] | None = None  # [{blob_id, caption}] from prior uploads


@router.post("/content")
def content_feedback(req: ContentFeedbackReq) -> dict:
    g = check(req.feedback_md, entry_point="content_feedback", user_id=req.user_id)
    ctx = _interaction_context(req.interaction_id)
    path = save_content_feedback(
        interaction_id=req.interaction_id, user_id=req.user_id,
        course_name=ctx["course"], subtopic_name=ctx["subtopic"],
        interaction_type=ctx["type"], dl=ctx["dl"], feedback_md=g.sanitized_text,
        image_links=req.image_links or [],
    )
    return {"saved": True, "md_file_path": path}


@router.post("/content/upload")
async def content_feedback_upload(
    interaction_id: str = Form(...),
    feedback_md: str = Form(...),
    caption: str = Form(""),
    user_id: str = Form(""),
    image: UploadFile = File(...),
) -> dict:
    """Content feedback with a single linked image (spec 06 §2). The caption is the text
    the image is linked to; both are embedded inline in the .md."""
    g = check(feedback_md, entry_point="content_feedback", user_id=user_id or None)
    ctx = _interaction_context(interaction_id)
    data = await image.read()
    from app.feedback import store_feedback_image

    link = store_feedback_image(data, image.content_type or "image/png", caption)
    path = save_content_feedback(
        interaction_id=interaction_id, user_id=user_id or None,
        course_name=ctx["course"], subtopic_name=ctx["subtopic"],
        interaction_type=ctx["type"], dl=ctx["dl"], feedback_md=g.sanitized_text,
        image_links=[link],
    )
    return {"saved": True, "md_file_path": path}


class AppFeedbackReq(BaseModel):
    page_key: str
    feedback_md: str
    user_id: str | None = None


@router.post("/application")
def application_feedback(req: AppFeedbackReq) -> dict:
    g = check(req.feedback_md, entry_point="app_feedback", user_id=req.user_id)
    fid = save_application_feedback(page_key=req.page_key, user_id=req.user_id,
                                    feedback_md=g.sanitized_text)
    return {"saved": True, "feedback_id": fid}
