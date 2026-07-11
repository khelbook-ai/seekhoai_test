"""Follow-up Q&A generation + Weakness Remediation Reserve (spec 04 §4, 05 §10).

A learner reaches Q&A ONLY as a follow-up after a wrong MCQ. To find the *root cause* of
the mistake we may ask several short follow-ups — but generating those at runtime must be
FAST, so we never scrape the web mid-session. Instead, at BUILD time the Root-Cause
Weakness agent decides what extra material to gather and we stash it on the subtopic as a
`reserve`. Runtime probe Q&A are generated from that reserve with a single LLM call.
"""
from __future__ import annotations

from app import events
from app.agents.generators.content import _package_text
from app.llm import complete_json
from app.prompts import render


def _reserve_text(reserve: dict, limit: int = 4500) -> str:
    if not reserve:
        return "(no reserve material)"
    parts = []
    misc = reserve.get("misconceptions", [])
    if misc:
        parts.append("COMMON MISCONCEPTIONS:\n" + "\n".join(
            f"- {m.get('root_cause')} → fix: {m.get('remediation')}" for m in misc[:6]))
    if reserve.get("prerequisite_gaps"):
        parts.append("PREREQUISITE GAPS:\n" + "\n".join(f"- {g}" for g in reserve["prerequisite_gaps"][:6]))
    snips = reserve.get("extra_snippets", [])
    if snips:
        parts.append("EXTRA REMEDIATION MATERIAL:\n" + "\n".join(s[:500] for s in snips[:4]))
    if reserve.get("package_digest"):
        parts.append("SUBTOPIC MATERIAL:\n" + reserve["package_digest"])
    return "\n\n".join(parts)[:limit]


def build_reserve(subtopic: dict, package: dict, intent: dict, domain_grounding: dict,
                  course_id: str | None = None) -> dict:
    """Root-Cause Weakness agent → misconception map + lightly-scouted extra material,
    stored as the subtopic's runtime reserve (build time only)."""
    from app.config import get_settings

    dg = domain_grounding or {}
    n_extra = int(get_settings().section("followup").get("reserve_extra_sources", 2))
    events.emit(course_id, "generation", "reserve",
                f"Root-Cause Weakness agent: mapping misconceptions for '{subtopic['name']}'")
    try:
        rc, _ = complete_json(
            "adaptive_controller", "You output only JSON.",
            render("root_cause_reserve", subtopic_name=subtopic["name"],
                   description=subtopic.get("description", ""), dl=subtopic.get("calibrated_dl", 2),
                   orientation=intent.get("orientation", "general"),
                   seniority=intent.get("seniority", "mid"),
                   domain=dg.get("domain", "general"), must_ground=dg.get("must_ground", False),
                   package=_package_text(package, limit=4000), extra_source_count=n_extra),
            phase="generation", max_tokens=1500, course_id=course_id)
    except Exception as e:  # never let reserve-building break a build
        events.emit(course_id, "generation", "warn", f"  ↳ root-cause agent failed ({str(e)[:50]}) — reserve from package only")
        rc = {}

    extra_snippets = _gather_extra(rc.get("search_queries", [])[:n_extra], course_id)
    reserve = {
        "misconceptions": rc.get("misconceptions", []),
        "prerequisite_gaps": rc.get("prerequisite_gaps", []),
        "extra_snippets": extra_snippets,
        "package_digest": _package_text(package, limit=2500),
    }
    events.emit(course_id, "generation", "reserve",
                f"  ↳ reserve: {len(reserve['misconceptions'])} misconceptions, "
                f"{len(extra_snippets)} extra snippets kept for runtime probes")
    return reserve


def _gather_extra(queries: list[str], course_id: str | None) -> list[str]:
    """Best-effort extra scouting for the reserve. Guarded: any failure yields no extra
    material (the misconception map alone is enough to generate probes)."""
    from app.mcp import router, tools

    snippets: list[str] = []
    for q in queries:
        try:
            events.emit(course_id, "generation", "reserve", f"  ↳ scouting extra material: \"{q[:60]}\"")
            res = tools.web_search(q, max_results=2, course_id=course_id)
            for r in (res.get("results") or [])[:1]:
                out = router.extract_url(r.get("url"), source_type="article")
                for c in (out.get("text_chunks") or [])[:2]:
                    if c.get("text"):
                        snippets.append(c["text"])
        except Exception:
            continue
    return snippets


def generate_seed_followup(subtopic: dict, package: dict, reserve: dict, intent: dict,
                           dl: int, course_id: str | None = None) -> dict:
    """Pre-generate the FIRST follow-up Q&A for a subtopic (spec 04 §4). Simple, conceptual,
    no equation-writing. Served immediately when the learner misses the MCQ."""
    misc = (reserve.get("misconceptions") or [{}])[0]
    return _generate_followup(subtopic, reserve, intent, dl, misc, course_id)


def generate_probe_followup(subtopic: dict, reserve: dict, intent: dict, dl: int,
                            probe_round: int, course_id: str | None = None) -> dict:
    """Runtime root-cause probe Q&A. Uses ONLY the stored reserve — no scraping (fast).
    Rotates through the mapped misconceptions as the learner keeps missing."""
    misc_list = reserve.get("misconceptions") or [{}]
    misc = misc_list[probe_round % len(misc_list)]
    return _generate_followup(subtopic, reserve, intent, dl, misc, course_id)


def _generate_followup(subtopic: dict, reserve: dict, intent: dict, dl: int,
                       misc: dict, course_id: str | None) -> dict:
    dg = subtopic.get("domain_grounding") or {}
    data, res = complete_json(
        "qa_generator", "You output only JSON.",
        render("gen_followup_qa", subtopic_name=subtopic["name"],
               description=subtopic.get("description", ""),
               orientation=intent.get("orientation", "general"),
               seniority=intent.get("seniority", "mid"),
               domain=dg.get("domain", "general"), must_ground=dg.get("must_ground", False),
               probe_focus=misc.get("probe_focus") or misc.get("root_cause") or "the core idea of this subtopic",
               remediation=misc.get("remediation") or "explain the concept simply",
               reserve=_reserve_text(reserve)),
        phase="generation", max_tokens=1800, course_id=course_id)
    data["_type"] = "qa"
    data["_dl"] = max(1, dl - 1)  # a follow-up is always easier than the MCQ it follows
    data["_gen"] = {"model": res.model, "tin": res.tokens_in, "tout": res.tokens_out,
                    "latency_ms": res.latency_ms}
    return data
