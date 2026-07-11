"""Guided code-walkthrough generator (spec 04 §1, 07 §2). Produces a small realistic code
example, a sequence of concept steps that highlight line ranges, and a paired MCQ that tests
the code. Generated only for technical learners. All line ranges are validated/clamped so the
UI can never be handed an out-of-bounds highlight.
"""
from __future__ import annotations

from app.agents.generators.content import _package_text
from app.llm import complete_json
from app.prompts import render


def _line_count(content: str) -> int:
    return max(1, len((content or "").split("\n")))


def _validate(data: dict) -> dict:
    """Clamp highlight ranges to each file's real line count and drop broken steps so the
    walkthrough is always internally consistent."""
    files = [f for f in (data.get("files") or []) if f.get("name") and f.get("content")]
    if not files:
        raise ValueError("walkthrough produced no files")
    nlines = {f["name"]: _line_count(f["content"]) for f in files}
    default_file = files[0]["name"]
    steps = []
    for s in data.get("steps") or []:
        fname = s.get("file") if s.get("file") in nlines else default_file
        n = nlines[fname]
        ranges = []
        for rng in s.get("highlight") or []:
            try:
                a, b = int(rng[0]), int(rng[1])
            except (TypeError, ValueError, IndexError):
                continue
            a, b = max(1, min(a, n)), max(1, min(b, n))
            if a > b:
                a, b = b, a
            ranges.append([a, b])
        if s.get("title"):
            steps.append({"title": s["title"], "concept_md": s.get("concept_md", ""),
                          "file": fname, "highlight": ranges})
    if not steps:
        raise ValueError("walkthrough produced no valid steps")
    return {"title": data.get("title") or "Code walkthrough", "files": files, "steps": steps}


def generate_walkthrough(subtopic: dict, package: dict, intent: dict, dl: int,
                         course_id: str | None = None) -> dict:
    """Returns {'walkthrough': {title, files, steps}, 'mcq': {...}} or raises on failure."""
    dg = package.get("domain_grounding", {}) or {}
    data, res = complete_json(
        "walkthrough_generator", "You output only JSON.",
        render("gen_walkthrough", subtopic_name=subtopic["name"],
               description=subtopic.get("description", ""), dl=dl,
               seniority=intent.get("seniority", "mid"),
               domain=dg.get("domain", "general"), must_ground=dg.get("must_ground", False),
               package=_package_text(package)),
        phase="generation", max_tokens=3500, course_id=course_id)
    wt = _validate(data if isinstance(data, dict) else {})
    mcq = data.get("mcq") if isinstance(data, dict) else None
    gen = {"model": res.model, "tin": res.tokens_in, "tout": res.tokens_out,
           "latency_ms": res.latency_ms}
    return {"walkthrough": wt, "mcq": mcq, "_gen": gen}
