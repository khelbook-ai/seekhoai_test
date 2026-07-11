"""Learning-session graph (spec 02 §3). Separate from the build graph on purpose: the
runtime only READS built content, so replay is token-free (06 §6).

The executable runtime is REST-driven in app.runtime (each learner action is a request),
which is the natural fit for an interactive UI and gives durable, resumable state via the
`responses`/`sessions` tables. This module wires the same steps into a LangGraph
StateGraph for spec fidelity and observability — the node bodies delegate to app.runtime.
"""
from __future__ import annotations

from typing import Any, TypedDict


class SessionState(TypedDict, total=False):
    session_id: str
    user_id: str
    course_id: str
    current_subtopic: str
    current_interaction: dict
    current_dl: int
    hints_used_this_item: int
    running_score: int
    weakness_counts: dict
    action: dict          # {kind: 'answer'|'hint'|'content', ...}
    last_result: dict


def load_topic(state: SessionState) -> SessionState:
    from app import runtime

    state["current_interaction"] = runtime.current_interaction(state["session_id"])
    return state


def serve_interaction(state: SessionState) -> SessionState:
    # first item for any subtopic is the definition MCQ (guaranteed by generation ordering)
    from app import runtime

    state["current_interaction"] = runtime.current_interaction(state["session_id"])
    return state


def grade_response(state: SessionState) -> SessionState:
    from app import runtime

    a = state.get("action", {})
    state["last_result"] = runtime.submit_answer(
        state["session_id"], a["interaction_id"],
        selected_label=a.get("selected_label"), answer_text=a.get("answer_text"))
    return state


def escalate_qa(state: SessionState) -> SessionState:
    # escalation is handled inside runtime.submit_answer (sets a pending same-subtopic Q&A)
    return state


def record_score(state: SessionState) -> SessionState:
    state["running_score"] = (state.get("last_result") or {}).get("running_score", 0)
    return state


def flag_weakness(state: SessionState) -> SessionState:
    # weakness flagging happens inside runtime.submit_answer per spec 04 §6
    return state


def adaptive_next(state: SessionState) -> SessionState:
    from app import runtime

    state["current_interaction"] = runtime.current_interaction(state["session_id"])
    return state


def build_session_graph() -> Any:
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(SessionState)
    for name, fn in [
        ("load_topic", load_topic),
        ("serve_interaction", serve_interaction),
        ("grade_response", grade_response),
        ("escalate_qa", escalate_qa),
        ("record_score", record_score),
        ("flag_weakness", flag_weakness),
        ("adaptive_next", adaptive_next),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "load_topic")
    g.add_edge("load_topic", "serve_interaction")
    g.add_edge("serve_interaction", "grade_response")
    g.add_edge("grade_response", "escalate_qa")
    g.add_edge("escalate_qa", "record_score")
    g.add_edge("record_score", "flag_weakness")
    g.add_edge("flag_weakness", "adaptive_next")
    g.add_edge("adaptive_next", END)
    return g.compile()
