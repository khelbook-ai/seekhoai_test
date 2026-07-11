"""User signup + profile API (spec 01 §5, 03 §13). Name-only signup; the user id ties a
learner's courses/answers/weaknesses together so the Personalization agent can tune to them."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents import personalize
from app.store import create_user, get_user

router = APIRouter(prefix="/api/users", tags=["users"])


class SignUp(BaseModel):
    name: str


@router.post("")
def signup(req: SignUp) -> dict:
    return create_user(req.name)


@router.get("/{user_id}")
def profile(user_id: str) -> dict:
    u = get_user(user_id)
    if not u:
        raise HTTPException(404, "user not found")
    return u


@router.post("/{user_id}/refresh-profile")
def refresh(user_id: str) -> dict:
    if not get_user(user_id):
        raise HTTPException(404, "user not found")
    return personalize.refresh_profile(user_id)
