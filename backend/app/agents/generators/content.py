"""Interaction generators (spec 03 §7a-e). Produces MCQ / Q&A interaction bundles
(question, options|rubric, personalized content panel, 3-rung hint ladder, optional
diagram) grounded ONLY in the subtopic's Content Package + IntentProfile.

The FIRST interaction of every subtopic is the definition MCQ (04 §1).
"""
from __future__ import annotations

from app.llm import complete_json
from app.prompts import render


def _package_text(package: dict, limit: int = 6000) -> str:
    ex = package["extracted"]
    defs = "\n".join(f"- {d.get('term')}: {d.get('definition')}"
                     for d in ex.get("definitions", [])[:8])
    claims = "\n".join(f"- {c.get('text')}" for c in ex.get("key_claims", [])[:12])
    chunks = "\n".join(c.get("text", "")[:600] for c in ex.get("text_chunks", [])[:4])
    out = f"DEFINITIONS:\n{defs}\n\nKEY CLAIMS:\n{claims}\n\nSOURCE EXCERPTS:\n{chunks}"
    return out[:limit]


def _common_args(subtopic: dict, package: dict, intent: dict, dl: int) -> dict:
    dg = package.get("domain_grounding", {}) or {}
    return dict(
        subtopic_name=subtopic["name"], description=subtopic.get("description", ""),
        dl=dl, orientation=intent.get("orientation", "general"),
        seniority=intent.get("seniority", "mid"),
        domain=dg.get("domain", "general"), must_ground=dg.get("must_ground", False),
        package=_package_text(package),
    )


def generate_mcq(subtopic: dict, package: dict, intent: dict, dl: int,
                 *, definition: bool = False, course_id: str | None = None) -> dict:
    args = _common_args(subtopic, package, intent, dl)
    args["definition_note"] = (
        f"This is the FIRST interaction: it MUST be a DEFINITION MCQ asking what "
        f"'{subtopic['name']}' is." if definition else
        "This is a concept-check MCQ (not the definition question).")
    data, res = complete_json("mcq_generator", "You output only JSON.",
                              render("gen_mcq", **args), phase="generation",
                              max_tokens=3000, course_id=course_id)
    data["_type"] = "mcq"
    data["_dl"] = dl
    data["_gen"] = {"model": res.model, "tin": res.tokens_in, "tout": res.tokens_out,
                    "latency_ms": res.latency_ms}
    return data


def generate_qa(subtopic: dict, package: dict, intent: dict, dl: int,
                *, course_id: str | None = None) -> dict:
    args = _common_args(subtopic, package, intent, dl)
    data, res = complete_json("qa_generator", "You output only JSON.",
                              render("gen_qa", **args), phase="generation",
                              max_tokens=3000, course_id=course_id)
    data["_type"] = "qa"
    data["_dl"] = dl
    data["_gen"] = {"model": res.model, "tin": res.tokens_in, "tout": res.tokens_out,
                    "latency_ms": res.latency_ms}
    return data


def generate_svg_diagram(what: str, subtopic_name: str, course_id: str | None = None) -> str | None:
    """Generate a simple SVG schematic when no sourced figure exists (05 §6, D8)."""
    try:
        data, _ = complete_json("diagram_agent", "You output only JSON.",
                                render("gen_diagram", what=what, subtopic_name=subtopic_name),
                                phase="generation", max_tokens=2500, course_id=course_id)
        svg = data.get("svg") if isinstance(data, dict) else None
        return svg if svg and "<svg" in svg else None
    except Exception:
        return None


def plan_interactions(package: dict) -> list[dict]:
    """Decide the MCQ/Q&A mix and DL ladder for a subtopic (04 §1: first = definition MCQ).
    Returns a list of {kind, dl, definition} specs of length target_question_count."""
    q = max(1, int(package.get("target_question_count", 4)))
    base_dl = int(package.get("_dl", 2))
    specs = [{"kind": "mcq", "dl": base_dl, "definition": True}]
    for i in range(1, q):
        # alternate MCQ / Q&A; nudge DL up on later items within the subtopic
        kind = "qa" if i % 2 == 1 else "mcq"
        dl = min(3, base_dl + (1 if i >= q - 1 else 0))
        specs.append({"kind": kind, "dl": dl, "definition": False})
    return specs
