"""Cost Reconciliation (spec 03 §6b, 06 §5). Sums actual cost from generation_metrics,
computes delta vs estimate, and explains it. Writes to courses.cost_actual/delta/recon.
"""
from __future__ import annotations

from app import metrics
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
    return recon
