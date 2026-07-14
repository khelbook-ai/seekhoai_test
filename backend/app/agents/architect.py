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
    p = ctx.personalization or {}
    persona_note = "(new learner — no history yet)"
    if p.get("summary_md") or p.get("weak_areas"):
        weak = ", ".join(w.get("subtopic", "") for w in (p.get("weak_areas") or [])[:5])
        persona_note = (f"{p.get('summary_md', '')} "
                        f"Reinforce where they've struggled before: {weak or 'n/a'}. "
                        f"Directives: {p.get('directives', {})}").strip()
    data, _ = complete_json(
        "course_architect",
        "You output ONLY valid JSON matching the requested shape.",
        render("course_architect",
               raw_prompt=ctx.raw_prompt, raw_role=ctx.raw_role or "(unspecified)",
               orientation=ctx.intent.orientation, seniority=ctx.intent.seniority,
               domain=ctx.domain_grounding.domain, must_ground=ctx.domain_grounding.must_ground,
               currency_mode=ctx.currency_mode, clarifications=clar,
               assumptions="; ".join(ctx.assumptions) or "(none)",
               personalization=persona_note,
               seed_material=(ctx.seed_material[:6000] if ctx.seed_material else "(none)")),
        phase="generation", max_tokens=4000,
    )
    if isinstance(data, dict) and data.get("refusal"):
        raise ArchitectRefusal(data["refusal"], data.get("suggested_reframing", ""))
    return Curriculum(**data)
