"""Adaptive Controller (spec 03 §12, 04 §5-6). Mostly rules with light judgment:
DL adaptation, weakness flagging, and the MCQ→Q&A escalation rule. Thresholds live in
config, not code.
"""
from __future__ import annotations

from app.config import get_settings


def working_dl(base_dl: int, recent: list[dict]) -> int:
    """Adapt the learner's working DL from recent responses in the current topic.
    Promote after PROMOTE_STREAK correct with <1 hint; demote after DEMOTE_ERRORS errors.
    `recent` is newest-last: [{correct: bool, hints_used: int, band: str|None}]."""
    cfg = get_settings().section("adaptivity")
    promote = int(cfg.get("promote_streak", 2))
    demote = int(cfg.get("demote_errors", 2))
    dl = base_dl

    streak_ok = 0
    streak_err = 0
    for r in recent:
        ok = bool(r.get("correct")) and (r.get("band") in (None, "full", "partial"))
        low_hint = int(r.get("hints_used", 0)) < 1
        if ok and low_hint:
            streak_ok += 1
            streak_err = 0
        elif not ok:
            streak_err += 1
            streak_ok = 0
        else:
            streak_ok = 0
        if streak_ok >= promote:
            dl = min(3, dl + 1)
            streak_ok = 0
        if streak_err >= demote:
            dl = max(1, dl - 1)
            streak_err = 0
    return dl


def is_weakness(*, interaction_type: str, correct: bool, band: str | None) -> bool:
    """WEAKNESS_THRESHOLD (D5): wrong MCQ, or Q&A incorrect/partial."""
    if interaction_type == "mcq":
        return not correct
    return band in ("incorrect", "partial")
