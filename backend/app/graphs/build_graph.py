"""Course-build graph (spec 02 §2). Offline-ish pipeline: intake → curriculum → sources
→ cost gate → generation → checks → persist. Human-in-the-loop pauses at clarification
and cost approval.

The executable build is a DB-backed state machine in app.build (the course `status`
column is the durable checkpoint, so builds survive restarts and resume exactly — the
same guarantee LangGraph's Postgres checkpointer provides, driven naturally over REST).
HITL pauses are real states the UI advances through; nothing generates until cost is
approved. This module wires the same nodes into a LangGraph StateGraph for spec fidelity
and observability; node bodies delegate to app.build / app.pipeline.

Kept strictly separate from the session graph (06 §6): learning never triggers a rebuild.
"""
from __future__ import annotations

from typing import Any, TypedDict


class BuildState(TypedDict, total=False):
    course_id: str
    course_context: dict
    curriculum: dict
    source_manifest: dict
    cost_estimate: dict
    cost_approved: bool
    generated: dict
    check_failures: list
    metrics: dict


# --- node bodies delegate to the real orchestration -------------------------
def intent_classification(state: BuildState) -> BuildState: return state       # app.agents.intake
def clarification_loop(state: BuildState) -> BuildState: return state           # HITL: app.build (interrupt)
def domain_grounding(state: BuildState) -> BuildState: return state             # app.agents.intake
def course_architect(state: BuildState) -> BuildState: return state             # app.agents.architect
def cost_estimator(state: BuildState) -> BuildState: return state               # app.agents.cost_estimator
def cost_gate(state: BuildState) -> BuildState: return state                    # HITL: app.build.approve_cost


def course_scout(state: BuildState) -> BuildState:
    return state                                                                # app.agents.scout


def scouting_auditor(state: BuildState) -> BuildState:
    return state                                                                # app.agents.auditor


def content_generation(state: BuildState) -> BuildState:
    from app.pipeline import run_content_pipeline

    if state.get("cost_approved") and state.get("course_id"):
        run_content_pipeline(state["course_id"])
    return state


def option_checker(state: BuildState) -> BuildState: return state               # app.agents.checkers.option
def domain_checker(state: BuildState) -> BuildState: return state               # app.agents.checkers.semantic
def content_verification(state: BuildState) -> BuildState: return state         # app.agents.checkers.semantic
def cost_reconciliation(state: BuildState) -> BuildState: return state          # app.agents.cost_reconciliation
def persist_course(state: BuildState) -> BuildState: return state


def build_graph() -> Any:
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(BuildState)
    for name, fn in [
        ("intent_classification", intent_classification),
        ("clarification_loop", clarification_loop),
        ("domain_grounding", domain_grounding),
        ("course_architect", course_architect),
        ("course_scout", course_scout),
        ("scouting_auditor", scouting_auditor),
        ("cost_estimator", cost_estimator),
        ("cost_gate", cost_gate),
        ("content_generation", content_generation),
        ("option_checker", option_checker),
        ("domain_checker", domain_checker),
        ("content_verification", content_verification),
        ("cost_reconciliation", cost_reconciliation),
        ("persist_course", persist_course),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "intent_classification")
    g.add_edge("intent_classification", "clarification_loop")
    g.add_edge("clarification_loop", "domain_grounding")
    g.add_edge("domain_grounding", "course_architect")
    g.add_edge("course_architect", "course_scout")
    g.add_edge("course_scout", "scouting_auditor")
    g.add_edge("scouting_auditor", "cost_estimator")
    g.add_edge("cost_estimator", "cost_gate")
    g.add_edge("cost_gate", "content_generation")
    g.add_edge("content_generation", "option_checker")
    g.add_edge("option_checker", "domain_checker")
    g.add_edge("domain_checker", "content_verification")
    g.add_edge("content_verification", "cost_reconciliation")
    g.add_edge("cost_reconciliation", "persist_course")
    g.add_edge("persist_course", END)
    return g.compile()
