"""Global cost-history utility (spec 03 §6, 06 §5). A cross-user / cross-session record of
every build's estimated-vs-actual cost, indexing the reconciliation .md files. Used two ways:

  record()      — after a build, append this course's estimate/actual (called by the reconciler)
  calibration() — before a build, find SIMILAR past courses and derive a correction factor so
                  the new estimate reflects how estimates actually panned out for that kind of
                  course. Only similar courses (keyword Jaccard over a threshold) are used.
"""
from __future__ import annotations

import json
import re
import statistics

from app.config import get_settings
from app.db import execute, fetchall

_STOP = {"the", "a", "an", "of", "and", "or", "to", "in", "for", "with", "on", "how", "what",
         "understanding", "introduction", "advanced", "basics", "fundamentals", "course", "topics"}


def signature(title: str, subtopic_names: list[str], domain: str | None) -> list[str]:
    """Normalized keyword set describing a course, for similarity matching."""
    text = " ".join([title or ""] + list(subtopic_names or []) + [domain or ""]).lower()
    toks = {t for t in re.split(r"[^a-z0-9]+", text) if len(t) > 2 and t not in _STOP}
    return sorted(toks)


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def record(course_id: str, title: str, domain: str | None, currency_mode: str,
           keywords: list[str], estimated: float, actual: float, delta_pct: float,
           md_path: str | None) -> None:
    ratio = round(actual / estimated, 4) if estimated else None
    execute(
        """INSERT INTO cost_history
             (course_id, title, domain, currency_mode, keywords, estimated, actual, delta_pct, ratio, md_path)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (course_id, title, domain, currency_mode, json.dumps(keywords), estimated, actual,
         delta_pct, ratio, md_path),
    )


def calibration(keywords: list[str], currency_mode: str) -> dict | None:
    """Find similar past builds and return a correction factor (median actual/estimated).
    Returns None when there aren't enough SIMILAR courses to trust a correction."""
    cfg = get_settings().section("cost")
    min_overlap = float(cfg.get("calibration_min_overlap", 0.34))
    min_samples = int(cfg.get("calibration_min_samples", 1))
    kw = set(keywords)
    rows = fetchall(
        "SELECT course_id, title, keywords, ratio, currency_mode, delta_pct, md_path "
        "FROM cost_history WHERE ratio IS NOT NULL ORDER BY created_at DESC LIMIT 200")
    similar = []
    for r in rows:
        sim = _jaccard(kw, set(r["keywords"] or []))
        if sim >= min_overlap:
            # a currency-mode match makes the ratio more comparable; keep others but rank lower
            similar.append({"title": r["title"], "ratio": float(r["ratio"]), "similarity": round(sim, 3),
                            "delta_pct": float(r["delta_pct"]) if r["delta_pct"] is not None else None,
                            "md_path": r["md_path"], "same_mode": r["currency_mode"] == currency_mode})
    if len(similar) < min_samples:
        return None
    similar.sort(key=lambda x: (x["same_mode"], x["similarity"]), reverse=True)
    used = similar[:5]
    factor = round(statistics.median(x["ratio"] for x in used), 4)
    return {"factor": factor, "samples": len(used), "based_on": used}
