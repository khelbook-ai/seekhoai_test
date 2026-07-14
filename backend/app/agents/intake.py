"""Intake agents (spec 01, 03 §1-3): intent classification, domain grounding,
clarification. Fast model, strict-JSON output."""
from __future__ import annotations

from app.config import get_settings
from app.llm import complete_json
from app.prompts import render
from app.schemas import (
    ClarificationQ,
    CourseContext,
    DomainGrounding,
    IntentProfile,
)

_SYS = "You output ONLY valid JSON. No prose, no fences."


def classify_intent(raw_prompt: str, raw_role: str) -> IntentProfile:
    data, _ = complete_json(
        "intent_classification", _SYS,
        render("intent", raw_prompt=raw_prompt, raw_role=raw_role or "(unspecified)"),
        phase="intake", max_tokens=1200,
    )
    try:
        return IntentProfile(**data)
    except Exception:
        return IntentProfile()


def ground_domain(raw_prompt: str, raw_role: str, intent: IntentProfile) -> DomainGrounding:
    data, _ = complete_json(
        "domain_grounding", _SYS,
        render("domain_grounding", raw_prompt=raw_prompt, raw_role=raw_role or "(unspecified)",
               orientation=intent.orientation),
        phase="intake", max_tokens=1200,
    )
    try:
        return DomainGrounding(**data)
    except Exception:
        return DomainGrounding()


def clarification_questions(
    raw_prompt: str, raw_role: str, intent: IntentProfile, domain: DomainGrounding
) -> tuple[list[ClarificationQ], list[str]]:
    """Return (questions, assumptions). Zero questions when confident & unambiguous (D6)."""
    cfg = get_settings().section("clarification")
    max_q = int(cfg.get("max_questions", 10))
    # zero-question condition (spec 01 §3 / D6)
    if intent.confidence >= 0.85 and not intent.needs_clarification and (
        domain.must_ground is False or domain.confidence >= 0.7
    ):
        return [], []
    data, _ = complete_json(
        "clarification", _SYS,
        render("clarification", raw_prompt=raw_prompt, raw_role=raw_role or "(unspecified)",
               orientation=intent.orientation, seniority=intent.seniority,
               confidence=round(intent.confidence, 2), domain=domain.domain,
               must_ground=domain.must_ground, max_questions=max_q),
        phase="intake", max_tokens=1600,
    )
    qs = [ClarificationQ(**q) for q in (data.get("questions") or [])[:max_q]]
    return qs, list(data.get("assumptions_made") or [])


def infer_currency_mode(answers: list[ClarificationQ]) -> str:
    """latest_research if any clarification answer signals recency/currency."""
    joined = " ".join((a.answer or "") + " " + a.q for a in answers).lower()
    if any(k in joined for k in ("recent", "latest", "current", "stay updated",
                                 "new research", "cutting edge", "state of the art")):
        return "latest_research"
    return "fundamentals"


def build_course_context(
    *, user_id: str | None, raw_prompt: str, raw_role: str,
    intent: IntentProfile, domain: DomainGrounding,
    clarifications: list[ClarificationQ], assumptions: list[str],
    personalization: dict | None = None, seed_material: str = "",
) -> CourseContext:
    return CourseContext(
        user_id=user_id, raw_prompt=raw_prompt, raw_role=raw_role,
        intent=intent, domain_grounding=domain, clarifications=clarifications,
        currency_mode=infer_currency_mode(clarifications), assumptions=assumptions,
        personalization=personalization or {}, seed_material=seed_material or "",
    )
