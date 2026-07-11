"""Serving + deterministic grading for the richer interaction types (spec 04 §1):
order-the-steps, fill-in-the-blanks, drag-drop architecture diagrams. Grading is pure
Python (no runtime LLM) so these behave exactly like an MCQ: correct/incorrect, then the
same Q&A root-cause escalation on a wrong answer.
"""
from __future__ import annotations

import random
import re

RICH_TYPES = {"order", "blanks", "dragdrop"}


def _rng(interaction_id: str) -> random.Random:
    return random.Random(f"seed:{interaction_id}")


def _shuffled(seq: list, seed: str) -> list:
    out = list(seq)
    _rng(seed).shuffle(out)
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def public_payload(interaction_id: str, itype: str, payload: dict) -> dict:
    """Learner-facing payload with the answer stripped and items presented in a stable
    shuffled order (so nothing is pre-solved)."""
    payload = payload or {}
    if itype == "order":
        items = _shuffled(payload.get("items", []), interaction_id + ":order")
        # guard: if the shuffle happens to match the answer, rotate by one
        if [i["id"] for i in items] == payload.get("correct_order") and len(items) > 1:
            items = items[1:] + items[:1]
        return {"items": items}
    if itype == "blanks":
        return {"segments": payload.get("segments", []),
                "blanks": [{"id": b["id"]} for b in payload.get("blanks", [])],
                "bank": payload.get("bank", [])}
    if itype == "dragdrop":
        return {"boxes": payload.get("boxes", []),
                "entities": _shuffled(payload.get("entities", []), interaction_id + ":dnd")}
    return {}


def grade(itype: str, payload: dict, response: dict) -> bool:
    """All-or-nothing correctness (like an MCQ). Malformed/empty responses are incorrect."""
    payload, response = payload or {}, response or {}
    try:
        if itype == "order":
            return list(response.get("order", [])) == list(payload.get("correct_order", []))
        if itype == "blanks":
            answers = {b["id"]: _norm(b["answer"]) for b in payload.get("blanks", [])}
            given = {str(k): _norm(v) for k, v in (response.get("answers") or {}).items()}
            return bool(answers) and all(given.get(bid) == ans for bid, ans in answers.items())
        if itype == "dragdrop":
            correct = {str(k): str(v) for k, v in (payload.get("correct_mapping") or {}).items()}
            given = {str(k): str(v) for k, v in (response.get("mapping") or {}).items()}
            return bool(correct) and given == correct
    except (TypeError, ValueError, AttributeError):
        return False
    return False


def review_payload(itype: str, payload: dict) -> dict:
    """Full payload incl. the correct answer, for read-only review of a completed item."""
    return payload or {}
