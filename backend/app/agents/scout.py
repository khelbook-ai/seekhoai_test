"""Course Scout + Content Package assembly (spec 03 §5, 05 §3). Discovers live-web
sources per subtopic, extracts via the MCP tools/router, and hands generation a
self-contained Content Package. Generators read ONLY the package (no re-scraping).
"""
from __future__ import annotations

from app.llm import complete_json
from app.mcp import router, tools
from app.prompts import render

_MAX_SOURCES_PER_ROUND = 3


def _plan(subtopic: dict, currency_mode: str, domain: str, extra: str = "") -> dict:
    data, _ = complete_json(
        "course_scout", "You output only JSON.",
        render("scout_plan", subtopic_name=subtopic["name"],
               description=subtopic.get("description", ""), dl=subtopic["calibrated_dl"],
               currency_mode=currency_mode, domain=domain, extra=extra),
        phase="scouting", max_tokens=1200, course_id=subtopic.get("course_id"),
    )
    return data if isinstance(data, dict) else {}


def _gather_sources(plan: dict, currency_mode: str, since: str | None) -> list[dict]:
    """Run searches, dedupe, and extract the top sources through the format router."""
    candidates: list[dict] = []
    seen: set[str] = set()

    for q in (plan.get("search_queries") or [])[:4]:
        res = tools.web_search(q, max_results=4)
        for r in res.get("results", []) or []:
            u = r.get("url")
            if u and u not in seen:
                seen.add(u)
                candidates.append({"url": u, "title": r.get("title"), "type": "article"})

    if currency_mode == "latest_research":
        for q in (plan.get("paper_queries") or [])[:2]:
            res = tools.paper_search(q, since=since, max_results=3)
            for r in res.get("results", []) or []:
                u = r.get("url")
                if u and u not in seen:
                    seen.add(u)
                    candidates.append({"url": u, "title": r.get("title"), "type": "paper",
                                       "published": r.get("published")})

    extracted: list[dict] = []
    for cand in candidates[: _MAX_SOURCES_PER_ROUND * 2]:
        if len([e for e in extracted if e.get("text_chunks")]) >= _MAX_SOURCES_PER_ROUND:
            break
        out = router.extract_url(cand["url"], source_type=cand.get("type"))
        if out.get("error") or not out.get("text_chunks"):
            continue
        blob_ref = out.get("_blob_ref")
        figs = router.figures_for(cand["url"], blob_ref)
        extracted.append({
            "url": cand["url"], "title": cand.get("title") or (out.get("meta") or {}).get("title"),
            "type": cand["type"], "published": cand.get("published") or (out.get("meta") or {}).get("published"),
            "text_chunks": out.get("text_chunks", []), "figures": figs,
            "license_hint": None,
        })
    return extracted


def _distill(subtopic: dict, plan: dict, sources: list[dict]) -> dict:
    material_parts = []
    for i, s in enumerate(sources):
        sid = f"s{i}"
        s["source_id"] = sid
        joined = "\n".join(c["text"] for c in s["text_chunks"][:6])
        material_parts.append(f"[{sid}] ({s.get('title') or s['url']}):\n{joined[:3500]}")
    material = "\n\n".join(material_parts) or "(no material extracted)"
    data, _ = complete_json(
        "course_scout", "You output only JSON.",
        render("scout_distill", subtopic_name=subtopic["name"],
               description=subtopic.get("description", ""),
               required_concepts=plan.get("required_concepts", []), material=material[:14000]),
        phase="scouting", max_tokens=2500, course_id=subtopic.get("course_id"),
    )
    return data if isinstance(data, dict) else {}


def scout_subtopic(subtopic: dict, *, currency_mode: str, domain_grounding: dict,
                   since: str | None = None, extra_actions: str = "") -> dict:
    """One scouting round → ContentPackage-shaped dict (+ meta the auditor uses)."""
    domain = domain_grounding.get("domain", "general")
    plan = _plan(subtopic, currency_mode, domain, extra=extra_actions)
    sources = _gather_sources(plan, currency_mode, since)
    distilled = _distill(subtopic, plan, sources) if sources else {}

    text_chunks, figures = [], []
    for s in sources:
        for c in s["text_chunks"]:
            text_chunks.append({**c, "source_id": s["source_id"]})
        for f in s["figures"]:
            figures.append({**f, "source_id": s["source_id"]})

    newest = None
    for s in sources:
        if s.get("published"):
            newest = max(newest or s["published"], s["published"])

    package = {
        "subtopic_id": subtopic["subtopic_id"],
        "coverage_map": {
            "required_concepts": plan.get("required_concepts", []),
            "covered_concepts": distilled.get("covered_concepts", []),
            "gaps": distilled.get("gaps", []),
        },
        "sources": [{"source_id": s["source_id"], "url": s["url"], "type": s["type"],
                     "title": s.get("title"), "published": s.get("published"),
                     "license_hint": s.get("license_hint")} for s in sources],
        "extracted": {
            "text_chunks": text_chunks,
            "figures": figures,
            "tables": [],
            "key_claims": distilled.get("key_claims", []),
            "definitions": distilled.get("definitions", []),
        },
        "domain_grounding": domain_grounding,
        "target_question_count": subtopic["target_question_count"],
        "recency": {"mode": currency_mode, "newest_source": newest},
        # meta for the auditor
        "_dl": subtopic["calibrated_dl"], "_plan": plan,
    }
    return package
