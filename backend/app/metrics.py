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


def full_course_cost(course_id: str) -> dict:
    """End-to-end token cost for a course (spec 03 §6b, 06 §5/§8): build phases PLUS all
    runtime spend attributed to this course. Build-time rows carry `course_id` directly;
    runtime rows (Q&A grading, root-cause probe generation) only carry `interaction_id`, so
    we also fold in any metrics whose interaction belongs to this course. Each row is counted
    once regardless of which condition matched.
    """
    from app.db import fetchall

    rows = fetchall(
        """
        SELECT COALESCE(phase, 'other')  AS phase,
               COALESCE(SUM(cost),0)      AS cost,
               COALESCE(SUM(tokens_in),0) AS tokens_in,
               COALESCE(SUM(tokens_out),0) AS tokens_out,
               COUNT(*)                   AS calls
        FROM generation_metrics gm
        WHERE gm.course_id = %s
           OR gm.interaction_id IN (
                SELECT i.id FROM interactions i
                JOIN subtopics s ON i.subtopic_id = s.id
                JOIN topics t ON s.topic_id = t.id
                WHERE t.course_id = %s)
        GROUP BY COALESCE(phase, 'other')
        """,
        (course_id, course_id),
    )
    by_phase = {
        r["phase"]: {
            "cost": float(r["cost"]),
            "tokens_in": int(r["tokens_in"]),
            "tokens_out": int(r["tokens_out"]),
            "calls": int(r["calls"]),
        }
        for r in rows
    }
    # Group phases into the buckets the user cares about (scouting / creation / Q&A feedback).
    buckets = {"scouting": 0.0, "creation": 0.0, "qa_feedback": 0.0, "other": 0.0}
    _BUCKET = {
        "scouting": "scouting", "intake": "scouting", "audit": "scouting",
        "generation": "creation", "checking": "creation", "verification": "creation",
        "grading": "qa_feedback", "followup": "qa_feedback", "chat": "qa_feedback",
    }
    for phase, p in by_phase.items():
        buckets[_BUCKET.get(phase, "other")] += p["cost"]
    return {
        "total": round(sum(p["cost"] for p in by_phase.values()), 6),
        "tokens_in": sum(p["tokens_in"] for p in by_phase.values()),
        "tokens_out": sum(p["tokens_out"] for p in by_phase.values()),
        "calls": sum(p["calls"] for p in by_phase.values()),
        "by_phase": by_phase,
        "buckets": {k: round(v, 6) for k, v in buckets.items()},
    }
