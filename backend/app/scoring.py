"""Scoring (spec 04 §3). Single place where item scores are computed.

Base score per interaction = DL * base_multiplier (default 2).
Minus hint_penalty (default 1) per hint used. Clamped to score_floor (default 0).
Wrong MCQ scores 0. Q&A uses partial-credit bands before the hint penalty.
"""
from __future__ import annotations

from app.config import ScoringConfig, get_settings


def mcq_score(dl: int, hints_used: int, correct: bool, cfg: ScoringConfig | None = None) -> int:
    cfg = cfg or get_settings().scoring
    if not correct:
        return 0
    raw = dl * cfg.base_multiplier - hints_used * cfg.hint_penalty
    return max(cfg.score_floor, raw)


def qa_score(dl: int, hints_used: int, band: str, cfg: ScoringConfig | None = None) -> int:
    """band in {full, partial, incorrect}. Fraction applies to base, then hints subtract."""
    cfg = cfg or get_settings().scoring
    frac = cfg.qa_partial_credit.get(band, 0.0)
    base = dl * cfg.base_multiplier * frac
    raw = round(base - hints_used * cfg.hint_penalty)
    return max(cfg.score_floor, raw)
