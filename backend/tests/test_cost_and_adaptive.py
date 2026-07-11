"""Cost Estimator math (spec 03 §6) and Adaptive Controller rules (spec 03 §12 / 04 §5)."""
from app.agents.adaptive import is_weakness, working_dl
from app.agents.cost_estimator import estimate
from app.schemas import Curriculum, SubtopicPlan, TopicPlan


def _curriculum(qs=(4, 4)):
    return Curriculum(title="t", topics=[
        TopicPlan(name="T1", order=1, calibrated_dl=2, subtopics=[
            SubtopicPlan(name=f"s{i}", order=i, target_question_count=q) for i, q in enumerate(qs)
        ])
    ])


def test_estimate_positive_and_buffered():
    est = estimate(_curriculum(), "fundamentals")
    assert est.total_estimate > 0
    assert est.buffer_pct == 15
    assert set(est.by_phase) == {"scouting", "generation", "checking", "verification"}
    # buffer means total >= raw sum of phases
    assert est.total_estimate >= sum(est.by_phase.values()) - 1e-9


def test_estimate_scales_with_questions():
    small = estimate(_curriculum((2,)), "fundamentals").total_estimate
    big = estimate(_curriculum((8,)), "fundamentals").total_estimate
    assert big > small


def test_latest_research_costs_more():
    fund = estimate(_curriculum(), "fundamentals").total_estimate
    latest = estimate(_curriculum(), "latest_research").total_estimate
    assert latest > fund  # recency multiplier on scouting


def test_working_dl_promotes_and_demotes():
    base = 2
    promote = [{"correct": True, "hints_used": 0, "band": None}] * 2
    assert working_dl(base, promote) == 3
    demote = [{"correct": False, "hints_used": 0, "band": None}] * 2
    assert working_dl(base, demote) == 1


def test_weakness_rules():
    assert is_weakness(interaction_type="mcq", correct=False, band=None)
    assert not is_weakness(interaction_type="mcq", correct=True, band=None)
    assert is_weakness(interaction_type="qa", correct=False, band="partial")
    assert not is_weakness(interaction_type="qa", correct=True, band="full")
