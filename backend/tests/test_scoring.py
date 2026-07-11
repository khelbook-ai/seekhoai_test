"""Scoring tests (spec 04 §3). Uses an explicit config — no DB/yaml needed."""
from app.config import ScoringConfig
from app.scoring import mcq_score, qa_score

CFG = ScoringConfig(
    base_multiplier=2,
    hint_penalty=1,
    score_floor=0,
    qa_partial_credit={"full": 1.0, "partial": 0.5, "incorrect": 0.0},
)


def test_mcq_base_by_dl():
    assert mcq_score(1, 0, True, CFG) == 2
    assert mcq_score(2, 0, True, CFG) == 4
    assert mcq_score(3, 0, True, CFG) == 6


def test_mcq_hint_penalty():
    assert mcq_score(2, 1, True, CFG) == 3
    assert mcq_score(2, 2, True, CFG) == 2
    assert mcq_score(3, 3, True, CFG) == 3


def test_mcq_wrong_is_zero():
    assert mcq_score(3, 0, False, CFG) == 0


def test_score_floor_clamps():
    # DL1 with 3 hints would be -1; floor clamps to 0.
    assert mcq_score(1, 3, True, CFG) == 0


def test_qa_partial_credit():
    assert qa_score(2, 0, "full", CFG) == 4
    assert qa_score(2, 0, "partial", CFG) == 2
    assert qa_score(2, 0, "incorrect", CFG) == 0


def test_qa_hint_penalty_after_fraction():
    # partial of DL2 base(4) = 2, minus 1 hint = 1
    assert qa_score(2, 1, "partial", CFG) == 1
