"""Course Architect (spec 03 §4). Strong model → calibrated Curriculum."""
from __future__ import annotations

from app.llm import complete_json
from app.prompts import render
from app.schemas import CourseContext, Curriculum


class ArchitectRefusal(Exception):
    def __init__(self, reason: str, reframing: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.reframing = reframing


def build_curriculum(ctx: CourseContext) -> Curriculum:
    clar = "; ".join(f"{c.q} -> {c.answer}" for c in ctx.clarifications) or "(none)"
    data, _ = complete_json(
        "course_architect",
        "You output ONLY valid JSON matching the requested shape.",
        render("course_architect",
               raw_prompt=ctx.raw_prompt, raw_role=ctx.raw_role or "(unspecified)",
               orientation=ctx.intent.orientation, seniority=ctx.intent.seniority,
               domain=ctx.domain_grounding.domain, must_ground=ctx.domain_grounding.must_ground,
               currency_mode=ctx.currency_mode, clarifications=clar,
               assumptions="; ".join(ctx.assumptions) or "(none)"),
        phase="generation", max_tokens=4000,
    )
    if isinstance(data, dict) and data.get("refusal"):
        raise ArchitectRefusal(data["refusal"], data.get("suggested_reframing", ""))
    return Curriculum(**data)
