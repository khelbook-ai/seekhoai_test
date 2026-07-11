"""Course Scout + Content Package assembly (spec 03 §5, 05 §3). Discovers live-web
sources per subtopic, extracts via the MCP tools/router, and hands generation a
self-contained Content Package. Generators read ONLY the package (no re-scraping).
"""
from __future__ import annotations

from app import events
from app.llm import complete_json
from app.mcp import router, tools
from app.prompts import render

_MAX_SOURCES_PER_ROUND = 3


def _plan(subtopic: dict, currency_mode: str, domain: str, extra: str = "") -> dict:
    cid = subtopic.get("course_id")
    events.emit(cid, "scouting", "plan", f"planning scout for '{subtopic['name']}' (DL{subtopic['calibrated_dl']})")
    data, _ = complete_json(
        "course_scout", "You output only JSON.",
        render("scout_plan", subtopic_name=subtopic["name"],
               description=subtopic.get("description", ""), dl=subtopic["calibrated_dl"],
               currency_mode=currency_mode, domain=domain, extra=extra),
        phase="scouting", max_tokens=1200, course_id=cid,
    )
    data = data if isinstance(data, dict) else {}
    events.emit(cid, "scouting", "plan",
                f"queries: {', '.join((data.get('search_queries') or [])[:4])}",
                {"required_concepts": data.get("required_concepts", [])})
    return data


def _gather_sources(plan: dict, currency_mode: str, since: str | None,
                    course_id: str | None = None) -> list[dict]:
    """Run searches, dedupe, and extract the top sources through the format router."""
    candidates: list[dict] = []
    seen: set[str] = set()

    for q in (plan.get("search_queries") or [])[:4]:
        res = tools.web_search(q, max_results=4, course_id=course_id)
        for r in res.get("results", []) or []:
            u = r.get("url")
            if u and u not in seen:
                seen.add(u)
                candidates.append({"url": u, "title": r.get("title"), "type": "article"})

    if currency_mode == "latest_research":
        for q in (plan.get("paper_queries") or [])[:2]:
            events.emit(course_id, "scouting", "mcp", f'paper_search (arXiv) "{q[:60]}"')
            res = tools.paper_search(q, since=since, max_results=3)
            for r in res.get("results", []) or []:
                u = r.get("url")
                if u and u not in seen:
                    seen.add(u)
                    candidates.append({"url": u, "title": r.get("title"), "type": "paper",
                                       "published": r.get("published")})

    # Extract candidate sources CONCURRENTLY (pure I/O — extractors don't decide relevance,
    # spec 05 §2), then deterministically keep the first N successful in candidate order —
    # exactly the same selection the serial early-break would make, just faster.
    from concurrent.futures import ThreadPoolExecutor

    pool_cands = candidates[: _MAX_SOURCES_PER_ROUND * 2]

    def _extract(cand: dict) -> tuple[dict, dict]:
        events.emit(course_id, "scouting", "scrape",
                    f"MCP extract [{cand.get('type')}] {cand['url'][:70]}")
        return cand, router.extract_url(cand["url"], source_type=cand.get("type"))

    outs: list[tuple[dict, dict]] = []
    if pool_cands:
        with ThreadPoolExecutor(max_workers=min(len(pool_cands), 4), thread_name_prefix="extract") as pool:
            futs = {pool.submit(_extract, c): i for i, c in enumerate(pool_cands)}
            tmp: dict[int, tuple[dict, dict]] = {}
            for fut, i in futs.items():
                tmp[i] = fut.result()
        outs = [tmp[i] for i in sorted(tmp)]  # restore candidate order

    extracted: list[dict] = []
    for cand, out in outs:
        if len(extracted) >= _MAX_SOURCES_PER_ROUND:
            break
        if out.get("error") or not out.get("text_chunks"):
            events.emit(course_id, "scouting", "scrape",
                        f"  ↳ skipped ({out.get('message','no usable text')[:50]})")
            continue
        events.emit(course_id, "scouting", "extract",
                    f"  ↳ extracted {len(out.get('text_chunks', []))} text chunks")
        figs = router.figures_for(cand["url"], out.get("_blob_ref"))  # figures only for kept sources
        extracted.append({
            "url": cand["url"], "title": cand.get("title") or (out.get("meta") or {}).get("title"),
            "type": cand["type"], "published": cand.get("published") or (out.get("meta") or {}).get("published"),
            "text_chunks": out.get("text_chunks", []), "figures": figs,
            "license_hint": None,
        })
    return extracted


def _distill(subtopic: dict, plan: dict, sources: list[dict]) -> dict:
    cid = subtopic.get("course_id")
    material_parts = []
    for i, s in enumerate(sources):
        sid = f"s{i}"
        s["source_id"] = sid
        joined = "\n".join(c["text"] for c in s["text_chunks"][:6])
        material_parts.append(f"[{sid}] ({s.get('title') or s['url']}):\n{joined[:3500]}")
    material = "\n\n".join(material_parts) or "(no material extracted)"
    events.emit(cid, "scouting", "distill",
                f"distilling Content Package from {len(sources)} sources")
    data, _ = complete_json(
        "course_scout", "You output only JSON.",
        render("scout_distill", subtopic_name=subtopic["name"],
               description=subtopic.get("description", ""),
               required_concepts=plan.get("required_concepts", []), material=material[:14000]),
        phase="scouting", max_tokens=2500, course_id=cid,
    )
    data = data if isinstance(data, dict) else {}
    events.emit(cid, "scouting", "distill",
                f"  ↳ {len(data.get('key_claims', []))} key claims, "
                f"{len(data.get('definitions', []))} definitions")
    return data


def scout_subtopic(subtopic: dict, *, currency_mode: str, domain_grounding: dict,
                   since: str | None = None, extra_actions: str = "") -> dict:
    """One scouting round → ContentPackage-shaped dict (+ meta the auditor uses)."""
    domain = domain_grounding.get("domain", "general")
    plan = _plan(subtopic, currency_mode, domain, extra=extra_actions)
    sources = _gather_sources(plan, currency_mode, since, course_id=subtopic.get("course_id"))
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
