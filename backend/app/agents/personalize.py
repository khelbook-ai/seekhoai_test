"""Personalization agent (spec 03 §13). A learner's identity (name-only signup) is the key
to *everything they've done*: their courses, answers, weaknesses, pace and accuracy. This
agent distills that history into a reusable profile — a short summary + structured directives
— that the Architect and Generators consume so each new course is tuned to this specific
learner (harder where they're strong, more scaffolding where they struggle).

It degrades gracefully: a brand-new learner with no history yields an empty profile, and any
LLM failure falls back to the deterministic signals alone.
"""
from __future__ import annotations

from app.db import fetchall, fetchone
from app.llm import complete_json
from app.prompts import render
from app.store import save_user_profile


def _signals(user_id: str) -> dict:
    """Deterministic stats from the learner's whole history (all their courses)."""
    acc = fetchone(
        """SELECT count(*) attempts, COALESCE(sum(CASE WHEN r.is_correct THEN 1 ELSE 0 END),0) correct,
                  COALESCE(avg(r.hints_used),0) avg_hints
           FROM responses r JOIN sessions se ON r.session_id = se.id
           WHERE se.user_id = %s""", (user_id,)) or {}
    weak = fetchall(
        """SELECT s.name subtopic, t.name topic, sum(w.error_count) errors
           FROM weaknesses w JOIN subtopics s ON w.subtopic_id = s.id
           JOIN topics t ON s.topic_id = t.id
           WHERE w.user_id = %s GROUP BY s.name, t.name ORDER BY errors DESC LIMIT 8""", (user_id,))
    courses = fetchall(
        """SELECT DISTINCT c.title FROM courses c JOIN sessions se ON se.course_id = c.id
           WHERE se.user_id = %s ORDER BY 1""", (user_id,))
    attempts = acc.get("attempts", 0) or 0
    return {
        "attempts": attempts,
        "accuracy_pct": round(100 * (acc.get("correct", 0) or 0) / attempts) if attempts else None,
        "avg_hints": round(float(acc.get("avg_hints", 0) or 0), 2),
        "weak_areas": [{"subtopic": w["subtopic"], "topic": w["topic"], "errors": int(w["errors"])} for w in weak],
        "past_courses": [c["title"] for c in courses],
    }


def refresh_profile(user_id: str) -> dict:
    """Recompute + persist the learner's profile from their history. Safe to call often
    (e.g. after finishing a session)."""
    if not user_id:
        return {}
    sig = _signals(user_id)
    name_row = fetchone("SELECT name FROM users WHERE id = %s", (user_id,))
    name = (name_row or {}).get("name") or "Learner"

    summary_md, directives = "", {}
    if sig["attempts"]:
        try:
            data, _ = complete_json(
                "personalization", "You output only JSON.",
                render("personalize", name=name, signals=sig), phase="intake", max_tokens=1200)
            summary_md = data.get("summary_md", "")
            directives = data.get("directives", {}) if isinstance(data.get("directives"), dict) else {}
        except Exception:
            summary_md = (f"{name} has answered {sig['attempts']} items at "
                          f"{sig['accuracy_pct']}% accuracy. Focus areas: "
                          + ", ".join(w["subtopic"] for w in sig["weak_areas"][:3]) + ".")
    save_user_profile(user_id, summary_md, directives, sig)
    return {"summary_md": summary_md, "directives": directives, "signals": sig}


def context_for_build(user_id: str | None) -> dict:
    """Compact personalization context injected into a new course build (Architect +
    Generators). Returns {} for anonymous or brand-new learners."""
    if not user_id:
        return {}
    prof = fetchone("SELECT summary_md, directives, signals FROM user_profiles WHERE user_id = %s",
                    (user_id,))
    if not prof:
        prof = refresh_profile(user_id) and fetchone(
            "SELECT summary_md, directives, signals FROM user_profiles WHERE user_id = %s", (user_id,))
    if not prof or not (prof.get("signals") or {}).get("attempts"):
        return {}
    return {"summary_md": prof.get("summary_md") or "",
            "directives": prof.get("directives") or {},
            "weak_areas": (prof.get("signals") or {}).get("weak_areas", [])}
