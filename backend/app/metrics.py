"""Generation metrics capture (spec 02 §5, 06 §1). Hard requirement: every agent/
tool call records model, tokens in/out, latency, and cost to `generation_metrics`.

Actual course cost (03 §6b) is an aggregation over these rows — no separate books.
"""
from __future__ import annotations

from app.db import execute


def record(
    *,
    phase: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    cost: float,
    course_id: str | None = None,
    interaction_id: str | None = None,
) -> None:
    """Insert one generation_metrics row. Never raise into the caller's path."""
    try:
        execute(
            """
            INSERT INTO generation_metrics
              (course_id, interaction_id, phase, model, tokens_in, tokens_out, latency_ms, cost)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (course_id, interaction_id, phase, model, tokens_in, tokens_out, latency_ms, cost),
        )
    except Exception:
        pass


def actual_cost(course_id: str) -> dict:
    """Sum actual cost + tokens for a course, overall and per phase (03 §6b, 06 §5)."""
    from app.db import fetchall

    rows = fetchall(
        """
        SELECT phase,
               COALESCE(SUM(cost),0)        AS cost,
               COALESCE(SUM(tokens_in),0)   AS tokens_in,
               COALESCE(SUM(tokens_out),0)  AS tokens_out,
               COUNT(*)                     AS calls
        FROM generation_metrics WHERE course_id = %s GROUP BY phase
        """,
        (course_id,),
    )
    by_phase = {
        r["phase"] or "other": {
            "cost": float(r["cost"]),
            "tokens_in": int(r["tokens_in"]),
            "tokens_out": int(r["tokens_out"]),
            "calls": int(r["calls"]),
        }
        for r in rows
    }
    total = round(sum(p["cost"] for p in by_phase.values()), 6)
    return {"total": total, "by_phase": by_phase}
