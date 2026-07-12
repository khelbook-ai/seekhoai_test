"""Cost Reconciliation (spec 03 §6b, 06 §5). Sums actual cost from generation_metrics,
computes delta vs estimate, and explains it. Writes to courses.cost_actual/delta/recon.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app import metrics
from app.config import get_settings
from app.db import fetchall, fetchone
from app.feedback import slugify
from app.llm import complete_json
from app.prompts import render
from app.store import get_course, update_course


def reconcile(course_id: str, notes: str = "") -> dict:
    course = get_course(course_id)
    est = (course.get("cost_estimate") or {})
    estimated = float(est.get("total_estimate", 0.0) or 0.0)
    act = metrics.actual_cost(course_id)
    actual = act["total"]
    delta_abs = round(actual - estimated, 5)
    delta_pct = round((delta_abs / estimated * 100) if estimated else 0.0, 1)
    act_by_phase = {k: round(v["cost"], 5) for k, v in act["by_phase"].items()}

    try:
        data, _ = complete_json(
            "cost_reconciliation", "You output only JSON.",
            render("cost_reconciliation", estimated=f"{estimated:.4f}", actual=f"{actual:.4f}",
                   delta_abs=f"{delta_abs:.4f}", delta_pct=delta_pct,
                   by_phase=act_by_phase, est_by_phase=est.get("by_phase", {}), notes=notes or "(none)"),
            phase="checking", max_tokens=1200, course_id=course_id)
    except Exception:
        data = {}
    recon = {
        "estimated": estimated, "actual": actual,
        "delta_abs": delta_abs, "delta_pct": delta_pct,
        "actual_by_phase": act_by_phase,
        "drivers": data.get("drivers", []) if isinstance(data, dict) else [],
        "summary": data.get("summary") if isinstance(data, dict) else "",
    }
    update_course(course_id, cost_actual=actual, cost_delta_abs=delta_abs,
                  cost_delta_pct=delta_pct, cost_reconciliation=recon)
    md_path = None
    try:
        md_path = _write_cost_md(course_id, course, recon)
        update_course(course_id, cost_md_path=md_path)
        recon["md_path"] = md_path
    except Exception:
        pass
    # Append to the GLOBAL cost history so future similar builds calibrate off this (06 §5).
    try:
        from app import cost_history
        from app.db import fetchall as _fa, fetchone as _fo

        subs = [r["name"] for r in _fa(
            "SELECT s.name FROM subtopics s JOIN topics t ON s.topic_id=t.id WHERE t.course_id=%s",
            (course_id,))]
        dom_row = _fo("SELECT ip.domain_grounding FROM courses c JOIN intent_profiles ip "
                      "ON ip.user_id=c.user_id WHERE c.id=%s ORDER BY ip.created_at DESC LIMIT 1",
                      (course_id,))
        domain = ((dom_row or {}).get("domain_grounding") or {}).get("domain")
        cost_history.record(course_id, course.get("title", ""), domain, course.get("currency_mode", ""),
                            cost_history.signature(course.get("title", ""), subs, domain),
                            estimated, actual, delta_pct, md_path)
    except Exception:
        pass
    return recon


def _write_cost_md(course_id: str, course: dict, recon: dict) -> str:
    """Persist the cost-delta reason + full build context to a .md file (spec 06 §5): which
    course, estimate vs actual, and how much scraping/generation/verification actually ran."""
    # build-activity context: how much web scraping / tool use / generation happened
    ev = {r["kind"]: r["n"] for r in fetchall(
        "SELECT kind, count(*) n FROM build_events WHERE course_id=%s GROUP BY kind", (course_id,))}
    phases = fetchall(
        "SELECT phase, count(*) calls, COALESCE(sum(tokens_in),0) tin, COALESCE(sum(tokens_out),0) tout, "
        "COALESCE(sum(cost),0) cost FROM generation_metrics WHERE course_id=%s GROUP BY phase ORDER BY phase",
        (course_id,))
    n_sources = fetchone(
        "SELECT count(*) n FROM sources so JOIN subtopics s ON so.subtopic_id=s.id "
        "JOIN topics t ON s.topic_id=t.id WHERE t.course_id=%s", (course_id,))["n"]
    n_subs = fetchone(
        "SELECT count(*) n FROM subtopics s JOIN topics t ON s.topic_id=t.id WHERE t.course_id=%s",
        (course_id,))["n"]
    n_reused = fetchone(
        "SELECT count(*) n FROM interactions i JOIN subtopics s ON i.subtopic_id=s.id "
        "JOIN topics t ON s.topic_id=t.id WHERE t.course_id=%s AND i.reused_from IS NOT NULL",
        (course_id,))["n"]

    drivers = "\n".join(
        f"- **{d.get('phase','?')}**: est ${float(d.get('estimated',0) or 0):.4f} → "
        f"actual ${float(d.get('actual',0) or 0):.4f} — {d.get('reason','')}"
        for d in (recon.get("drivers") or [])) or "- (no per-driver breakdown)"
    phase_rows = "\n".join(
        f"| {p['phase']} | {p['calls']} | {p['tin']} | {p['tout']} | ${float(p['cost']):.4f} |"
        for p in phases) or "| — | 0 | 0 | 0 | $0.0000 |"

    md = f"""---
course: "{course.get('title','')}"
course_id: "{course_id}"
currency_mode: "{course.get('currency_mode','')}"
estimated_usd: {recon['estimated']:.4f}
actual_usd: {recon['actual']:.4f}
delta_usd: {recon['delta_abs']:.4f}
delta_pct: {recon['delta_pct']}
generated_at: "{datetime.now(timezone.utc).isoformat()}"
---

# Cost reconciliation — {course.get('title','')}

**Estimated ${recon['estimated']:.4f} → actual ${recon['actual']:.4f}**
(delta **${recon['delta_abs']:.4f}**, **{recon['delta_pct']}%**).

## Why the delta
{recon.get('summary') or '(no summary)'}

### Per-phase drivers
{drivers}

## Build context (what actually ran)
- Subtopics built: **{n_subs}**  ·  interactions reused from library: **{n_reused}**
- Online sources used: **{n_sources}**
- Web searches: **{ev.get('web_search', 0)}**  ·  scrapes: **{ev.get('scrape', 0)}**  ·  \
extractions: **{ev.get('extract', 0)}**  ·  scout-again rounds: **{ev.get('round', 0)}**
- Generations: **{ev.get('generate', 0)}**  ·  domain/verify checks: \
**{ev.get('check', 0) + ev.get('verify', 0)}**  ·  reserve builds: **{ev.get('reserve', 0)}**

### Token + cost by phase
| Phase | Calls | Tokens in | Tokens out | Cost |
|-------|-------|-----------|------------|------|
{phase_rows}
"""
    out_dir = get_settings().data_dir / "cost"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slugify(course.get('title','course'))}-{course_id[:8]}.md"
    path.write_text(md, encoding="utf-8")
    return str(path)
