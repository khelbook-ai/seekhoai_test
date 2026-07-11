"""Domain + Verification checkers (spec 03 §9, §10). Domain uses the strong model;
Verification uses the independent Gemini model, checking claims against the package."""
from __future__ import annotations

from app.llm import complete_json
from app.prompts import render


def _answer_blob(item: dict) -> str:
    if item.get("_type") == "mcq":
        return "; ".join(f"{o.get('label')}:{o.get('text')}"
                         f"{'(correct)' if o.get('is_correct') else ''}"
                         for o in item.get("options", []))
    return str(item.get("qa_rubric", {}))


def domain_check(item: dict, subtopic: dict, domain_grounding: dict,
                 course_id: str | None = None) -> dict:
    data, _ = complete_json(
        "domain_checker", "You output only JSON.",
        render("domain_checker",
               domain=domain_grounding.get("domain", "general"),
               must_ground=domain_grounding.get("must_ground", False),
               subtopic_name=subtopic["name"], question=item.get("question_md", ""),
               answer_blob=_answer_blob(item)[:1500],
               content_panel=(item.get("content_panel_md", "") or "")[:1500]),
        phase="checking", max_tokens=800, course_id=course_id)
    if not isinstance(data, dict):
        return {"on_domain": True, "reason": "unparseable; passed", "regen_hint": None}
    return data


def verify(item: dict, subtopic: dict, package: dict, course_id: str | None = None) -> dict:
    ex = package.get("extracted", {})
    material = "KEY CLAIMS:\n" + "\n".join(f"- {c.get('text')}" for c in ex.get("key_claims", [])[:12])
    material += "\n\nDEFINITIONS:\n" + "\n".join(
        f"- {d.get('term')}: {d.get('definition')}" for d in ex.get("definitions", [])[:8])
    data, _ = complete_json(
        "content_verification", "You output only JSON.",
        render("verification", subtopic_name=subtopic["name"],
               question=item.get("question_md", ""), answer_blob=_answer_blob(item)[:1500],
               content_panel=(item.get("content_panel_md", "") or "")[:1500],
               material=material[:6000]),
        phase="verification", max_tokens=1000, course_id=course_id)
    if not isinstance(data, dict):
        return {"verdict": "pass", "issues": [], "suggested_fix": None}
    return data
