"""Q&A Grader (spec 03 §11). Grades a learner's free-text answer against the rubric and
returns a band + learner-facing feedback. Results are cached (D16) keyed by
(interaction_id, normalized answer) so re-testing the same answer costs no tokens.

The grader proposes the band; the scoring service computes the final number (04 §3).
"""
from __future__ import annotations

import json
import re

from app.db import execute, fetchone
from app.llm import complete_json
from app.prompts import render


def _norm(answer: str) -> str:
    return re.sub(r"\s+", " ", (answer or "").strip().lower())[:2000]


def grade(interaction: dict, answer: str) -> dict:
    """interaction: row with id, dl, question_md, qa_rubric, subtopic name.
    Returns {band, rubric_hits, rubric_misses, feedback_md, correct, cached}."""
    key = _norm(answer)
    cached = fetchone(
        "SELECT band, rubric_hits, rubric_misses, feedback_md FROM grader_cache "
        "WHERE interaction_id = %s AND answer_norm = %s", (interaction["id"], key))
    if cached:
        return {"band": cached["band"], "rubric_hits": cached["rubric_hits"] or [],
                "rubric_misses": cached["rubric_misses"] or [],
                "feedback_md": cached["feedback_md"], "correct": cached["band"] == "full",
                "cached": True}

    data, _ = complete_json(
        "qa_grader", "You output only JSON.",
        render("qa_grader", subtopic_name=interaction.get("subtopic", ""),
               dl=interaction.get("dl", 2), question=interaction.get("question_md", ""),
               rubric=json.dumps(interaction.get("qa_rubric") or {})[:2000],
               answer=answer[:2000]),
        # Compact judgment only (band + rubric hit/miss + a one-liner). The full correct
        # answer is pre-generated and served from the rubric, so the grader no longer writes
        # prose — small output keeps this call sub-second on the submit path.
        phase="grading", max_tokens=256, interaction_id=str(interaction["id"]))
    band = (data.get("raw_band") or "incorrect").lower()
    if band not in ("full", "partial", "incorrect"):
        band = "full" if data.get("correct") else "incorrect"
    result = {"band": band, "rubric_hits": data.get("rubric_hits", []),
              "rubric_misses": data.get("rubric_misses", []),
              "feedback_md": data.get("feedback_md", ""),
              "correct": band == "full", "cached": False}
    try:
        execute(
            "INSERT INTO grader_cache (interaction_id, answer_norm, band, rubric_hits, rubric_misses, feedback_md) "
            "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (interaction_id, answer_norm) DO NOTHING",
            (interaction["id"], key, band, json.dumps(result["rubric_hits"]),
             json.dumps(result["rubric_misses"]), result["feedback_md"]),
        )
    except Exception:
        pass
    return result
