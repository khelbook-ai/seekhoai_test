"""Option Checker (spec 03 §8): structure, answer-position variety, length balance."""
import random

from app.agents.checkers.option import check_and_fix


def _mcq(correct_idx, texts):
    return {"options": [{"text": t, "is_correct": i == correct_idx} for i, t in enumerate(texts)]}


def test_relabels_and_sets_answer_key():
    mcqs = [_mcq(0, ["right", "w1", "w2", "w3"])]
    res = check_and_fix(mcqs, rng=random.Random(1))
    m = res["items"][0]
    assert [o["label"] for o in m["options"]] == ["A", "B", "C", "D"]
    key = m["answer_key"]
    assert next(o for o in m["options"] if o["is_correct"])["label"] == key


def test_answer_position_variety():
    mcqs = [_mcq(0, [f"correct-{i}", "w", "w2", "w3"]) for i in range(8)]
    res = check_and_fix(mcqs, rng=random.Random(7))
    positions = [m["answer_key"] for m in res["items"]]
    # near-uniform across A-D, not all the same
    assert len(set(positions)) >= 3


def test_flags_length_imbalance():
    mcqs = [_mcq(0, ["a very long correct option that gives itself away easily", "no", "nope", "nah"])
            for _ in range(4)]
    res = check_and_fix(mcqs, rng=random.Random(3))
    assert any("systematically longer" in v for v in res["violations"])


def test_flags_wrong_option_count():
    mcqs = [{"options": [{"text": "a", "is_correct": True}, {"text": "b", "is_correct": False}]}]
    res = check_and_fix(mcqs, rng=random.Random(1))
    assert res["regen"] == [0]
    assert any("options" in v for v in res["violations"])
