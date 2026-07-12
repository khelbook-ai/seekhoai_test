"""Cost-history similarity signature + completion-time estimate (spec 03 §6, 06 §5, item 10).
Pure-function tests (no DB): the similarity signature must group like courses and the
completion estimate must scale with the curriculum."""
from app import cost_history
from app.agents.cost_estimator import _completion_minutes
from app.schemas import Curriculum, SubtopicPlan, TopicPlan


def _jac(a, b):
    return cost_history._jaccard(set(a), set(b))


def test_signature_groups_similar_courses():
    a = cost_history.signature("Reinforcement Learning Essentials", ["Policy gradients", "Q-learning"], "general")
    b = cost_history.signature("Deep Reinforcement Learning", ["Q-learning", "policy gradients", "actor critic"], "general")
    c = cost_history.signature("Transformer Attention Mechanisms", ["Self attention", "Positional encoding"], "general")
    assert _jac(a, b) >= 0.34          # RL courses are similar
    assert _jac(a, c) < 0.34           # RL vs transformers are not
    # stopwords/filler don't create false similarity
    assert "the" not in a and "fundamentals" not in a


def test_completion_scales_with_curriculum():
    small = Curriculum(title="X", topics=[TopicPlan(name="t", subtopics=[
        SubtopicPlan(name="s", target_question_count=3)])])
    big = Curriculum(title="Y", topics=[TopicPlan(name="t", subtopics=[
        SubtopicPlan(name="s1", target_question_count=6), SubtopicPlan(name="s2", target_question_count=6)])])
    assert _completion_minutes(big) > _completion_minutes(small) > 0
    # technical learners get code walkthroughs → more time than general
    assert _completion_minutes(small, "technical") > _completion_minutes(small, "general")
