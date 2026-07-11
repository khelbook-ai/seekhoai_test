"""Scouting Comprehensiveness Auditor (spec 03 §5b, 05 §4). Independent Sonnet-class
model gates generation until a subtopic's Content Package is genuinely comprehensive.
"""
from __future__ import annotations

from app.config import get_settings
from app.llm import complete_json
from app.prompts import render


def audit(package: dict, *, currency_mode: str) -> dict:
    cfg = get_settings().section("scouting")
    threshold = float(cfg.get("auditor_pass_threshold", 0.8))
    ex = package["extracted"]
    cov = package["coverage_map"]
    sources = package["sources"]
    src_desc = "; ".join(f"{s['type']}:{s.get('title') or s['url']}" for s in sources) or "(none)"

    data, _ = complete_json(
        "scouting_auditor", "You output only JSON.",
        render("scouting_auditor",
               subtopic_name=package.get("_plan", {}).get("subtopic_name", package["subtopic_id"]),
               dl=package.get("_dl", 2), currency_mode=currency_mode,
               required_concepts=cov.get("required_concepts", []),
               covered_concepts=cov.get("covered_concepts", []),
               n_sources=len(sources), sources=src_desc,
               n_chunks=len(ex.get("text_chunks", [])), n_figures=len(ex.get("figures", [])),
               n_claims=len(ex.get("key_claims", [])), n_defs=len(ex.get("definitions", [])),
               gaps=cov.get("gaps", []), threshold=threshold),
        phase="scouting", max_tokens=1500,
    )
    if not isinstance(data, dict):
        data = {}
    score = float(data.get("score", 0.0) or 0.0)
    comprehensive = bool(data.get("comprehensive", score >= threshold)) and score >= threshold
    return {"comprehensive": comprehensive, "score": score,
            "gaps": data.get("gaps", []), "recommended_actions": data.get("recommended_actions", [])}
