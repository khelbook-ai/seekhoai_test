"""Prompt Guardrail (spec 03 §0). Runs at every free-text input point:
course prompt, clarification answers, Q&A answers, and both feedback boxes.

Real classifier (fast model) + rule fallbacks. On a course-prompt violation we block;
on free-text answers/feedback we neutralise (sanitise + annotate) rather than execute
embedded instructions. Every verdict logs to guardrail_events. A trusted tester may
override a block with a logged reason (D19). Callers keep the same signature.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.db import execute
from app.prompts import render

MAX_LEN = 8000
_BLOCKING_POINTS = ("course_prompt", "clarify")
# `chat` is neutralised (sanitised, never hard-blocked): the RAG assistant is already confined
# to the course's own knowledge base, so an off-topic question simply gets "not covered here".
_NEUTRALISE_POINTS = ("qa_answer", "content_feedback", "app_feedback", "chat")

_INJECTION = re.compile(
    r"(ignore (all|previous|the above) instructions|system prompt|you are now|"
    r"disregard the above|reveal your (system )?prompt|jailbreak)",
    re.IGNORECASE,
)
# Obvious secrets to strip before persistence/logging.
_SECRET = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)",
)


@dataclass
class GuardrailResult:
    allow: bool
    category: str | None
    sanitized_text: str
    user_message: str | None


def _log(user_id: str | None, entry_point: str, raw_len: int, allow: bool,
         category: str | None, action: str) -> None:
    try:
        execute(
            """
            INSERT INTO guardrail_events (user_id, entry_point, raw_len, allow, category, action)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, entry_point, raw_len, allow, category, action),
        )
    except Exception:
        pass


def _classify_llm(text: str, entry_point: str) -> dict | None:
    """Ask the fast model. Returns dict or None if the call fails (fall back to rules)."""
    try:
        from app.llm import complete_json

        data, _ = complete_json(
            "prompt_guardrail",
            "You are a strict safety/relevance classifier. Output only JSON.",
            render("guardrail", entry_point=entry_point, text=text[:MAX_LEN]),
            phase="guardrail",
            max_tokens=1200,
        )
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def check(
    text: str,
    entry_point: str,
    user_id: str | None = None,
    *,
    tester_override: bool = False,
    override_reason: str | None = None,
) -> GuardrailResult:
    sanitized = (text or "").strip()

    # --- cheap deterministic guards first ---
    if len(sanitized) == 0:
        _log(user_id, entry_point, 0, False, "length", "blocked")
        return GuardrailResult(False, "length", "", "Please enter some text.")
    if len(sanitized) > MAX_LEN:
        _log(user_id, entry_point, len(text), False, "length", "blocked")
        return GuardrailResult(False, "length", sanitized[:MAX_LEN], "That input is too long.")

    # strip secrets everywhere before anything else touches the text
    if _SECRET.search(sanitized):
        sanitized = _SECRET.sub("[REDACTED]", sanitized)

    # --- LLM classifier (with rule fallback) ---
    verdict = _classify_llm(sanitized, entry_point)
    if verdict is None:
        category = "injection" if _INJECTION.search(sanitized) else None
        allow = not (category and entry_point in _BLOCKING_POINTS)
        user_message = None
        if category and entry_point in _BLOCKING_POINTS:
            user_message = "That prompt looks like it's trying to redirect the tool. Try rephrasing."
    else:
        category = verdict.get("category") if verdict.get("category") not in ("null", "", None) else None
        sanitized = (verdict.get("sanitized_text") or sanitized).strip() or sanitized
        allow = bool(verdict.get("allow", True))
        user_message = verdict.get("user_message")

    # neutralise (never block) on free-text answer/feedback points
    if entry_point in _NEUTRALISE_POINTS:
        allow = True
        user_message = None

    # trusted tester override of a block, with logged reason (D19)
    if not allow and tester_override:
        allow = True
        _log(user_id, entry_point, len(text), True, category, f"override:{override_reason or 'n/a'}")
        return GuardrailResult(True, category, sanitized, None)

    action = "allowed" if allow else "blocked"
    if allow and category:
        action = "sanitized"
    _log(user_id, entry_point, len(text), allow, category, action)
    return GuardrailResult(allow, category, sanitized, user_message if not allow else None)
