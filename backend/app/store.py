"""Persistence helpers for course intake + curriculum (spec 06 §1). Keeps SQL out of
the orchestration and API layers. Content persistence (interactions/options/hints/
diagrams) lives in app.build alongside generation.
"""
from __future__ import annotations

import json
from typing import Any

from app.db import execute, fetchall, fetchone


def ensure_user(role_raw: str | None) -> str:
    row = execute("INSERT INTO users (role_raw) VALUES (%s) RETURNING id", (role_raw,))
    return str(row["id"])


def create_course(*, user_id: str | None, title: str, raw_prompt: str,
                  currency_mode: str, status: str) -> str:
    row = execute(
        """
        INSERT INTO courses (user_id, title, raw_prompt, currency_mode, status)
        VALUES (%s,%s,%s,%s,%s) RETURNING id
        """,
        (user_id, title, raw_prompt, currency_mode, status),
    )
    return str(row["id"])


def update_course(course_id: str, **cols: Any) -> None:
    if not cols:
        return
    sets, params = [], []
    for k, v in cols.items():
        sets.append(f"{k} = %s")
        params.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
    params.append(course_id)
    execute(f"UPDATE courses SET {', '.join(sets)} WHERE id = %s", tuple(params))


def get_course(course_id: str) -> dict | None:
    return fetchone("SELECT * FROM courses WHERE id = %s", (course_id,))


def save_intent_profile(user_id: str | None, intent, domain) -> None:
    execute(
        """
        INSERT INTO intent_profiles (user_id, orientation, seniority, confidence, domain_grounding)
        VALUES (%s,%s,%s,%s,%s)
        """,
        (user_id, intent.orientation, intent.seniority, intent.confidence,
         json.dumps(domain.model_dump())),
    )


def save_clarifications(course_id: str, questions: list) -> None:
    for i, q in enumerate(questions):
        execute(
            """
            INSERT INTO clarification_qas (course_id, ordinal, question, options, answer, multi_select)
            VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (course_id, i, q.q, json.dumps(q.options), q.answer, bool(getattr(q, "multi_select", False))),
        )


def get_clarifications(course_id: str) -> list[dict]:
    return fetchall(
        "SELECT ordinal, question, options, answer, multi_select FROM clarification_qas "
        "WHERE course_id = %s ORDER BY ordinal", (course_id,))


def set_clarification_answers(course_id: str, answers: dict[int, str]) -> None:
    for ordinal, ans in answers.items():
        execute("UPDATE clarification_qas SET answer = %s WHERE course_id = %s AND ordinal = %s",
                (ans, course_id, ordinal))


def save_curriculum(course_id: str, curriculum) -> list[dict]:
    """Persist topics + subtopics; return the created subtopic rows (id + plan) in order."""
    execute("UPDATE courses SET curriculum = %s, title = %s WHERE id = %s",
            (json.dumps(curriculum.model_dump()), curriculum.title, course_id))
    created: list[dict] = []
    for topic in curriculum.topics:
        trow = execute(
            "INSERT INTO topics (course_id, name, ordinal, calibrated_dl, rationale) "
            "VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (course_id, topic.name, topic.order, topic.calibrated_dl, topic.rationale),
        )
        topic_id = str(trow["id"])
        for st in topic.subtopics:
            srow = execute(
                "INSERT INTO subtopics (topic_id, name, description, ordinal, target_question_count) "
                "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                (topic_id, st.name, st.description, st.order, st.target_question_count),
            )
            created.append({
                "subtopic_id": str(srow["id"]), "topic_id": topic_id,
                "topic_name": topic.name, "calibrated_dl": topic.calibrated_dl,
                "name": st.name, "description": st.description,
                "target_question_count": st.target_question_count,
            })
    return created


def list_subtopics(course_id: str) -> list[dict]:
    return fetchall(
        """
        SELECT s.id AS subtopic_id, s.name, s.description, s.target_question_count,
               s.partially_sourced, s.audit_score, t.calibrated_dl, t.name AS topic_name,
               t.ordinal AS topic_order, s.ordinal AS subtopic_order
        FROM subtopics s JOIN topics t ON s.topic_id = t.id
        WHERE t.course_id = %s ORDER BY t.ordinal, s.ordinal
        """,
        (course_id,),
    )
