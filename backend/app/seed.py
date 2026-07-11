"""Seed the Phase 0 slice: one AI subtopic + one DL2 definition MCQ.

Idempotent: uses fixed UUIDs so re-running does nothing new. No generation — this
is hand-authored so the learning screen has real content to render (spec 08 Phase 0).
"""
from __future__ import annotations

from app.db import cursor

COURSE_ID = "11111111-1111-1111-1111-111111111111"
TOPIC_ID = "22222222-2222-2222-2222-222222222222"
SUBTOPIC_ID = "33333333-3333-3333-3333-333333333333"
INTERACTION_ID = "44444444-4444-4444-4444-444444444444"

COURSE_NAME = "Understanding MCP"
SUBTOPIC_NAME = "MCP fundamentals"

CONTENT_PANEL = """\
**Model Context Protocol (MCP)** is an open standard that gives AI applications a
common way to connect to external tools and data sources. Instead of every app
building bespoke integrations for each tool, MCP defines a shared interface:

- an **MCP server** exposes tools, resources, and prompts;
- an **MCP client** (inside an AI app) discovers and calls them over that interface.

Think of it as a universal connector for AI apps — the same role a standard port
plays for hardware. It is not a model-internal trick, a storage format, or hardware.
"""

OPTIONS = [
    ("A", "A proprietary database format used to store large language model weights on disk.", False),
    ("B", "An open standard that lets AI applications connect to external tools and data sources through a common interface.", True),
    ("C", "A prompt-engineering technique that compresses long conversations into shorter summaries.", False),
    ("D", "A hardware accelerator specification for running transformer models on edge devices.", False),
]

HINTS = [
    (1, "The word *protocol* is the clue: it names a shared way for separate systems to talk to each other — not a storage detail or a hardware spec."),
    (2, "It is about standardizing how AI apps reach out to external tools and data — a common connector, rather than anything happening inside the model."),
    (3, "The correct answer is **B**: MCP is an open standard giving AI applications a common interface to connect to external tools and data sources."),
]


def seed() -> None:
    with cursor() as cur:
        cur.execute("SELECT 1 FROM interactions WHERE id = %s", (INTERACTION_ID,))
        if cur.fetchone():
            print("seed: already present, skipping")
            return

        cur.execute(
            "INSERT INTO courses (id, title, raw_prompt, currency_mode, accepted, status) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (COURSE_ID, COURSE_NAME, "Teach me about MCP", "fundamentals", True, "built"),
        )
        cur.execute(
            "INSERT INTO topics (id, course_id, name, ordinal, calibrated_dl) VALUES (%s,%s,%s,%s,%s)",
            (TOPIC_ID, COURSE_ID, "MCP", 1, 2),
        )
        cur.execute(
            "INSERT INTO subtopics (id, topic_id, name, description, ordinal, target_question_count) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (SUBTOPIC_ID, TOPIC_ID, SUBTOPIC_NAME, "What MCP is and why it exists.", 1, 5),
        )
        cur.execute(
            "INSERT INTO interactions (id, subtopic_id, type, dl, ordinal, question_md, "
            "content_panel_md, answer_key, gen_model, gen_latency_ms) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                INTERACTION_ID, SUBTOPIC_ID, "mcq", 2, 1,
                "What best defines the **Model Context Protocol (MCP)**?",
                CONTENT_PANEL, "B", "seed", 0,
            ),
        )
        for label, text, is_correct in OPTIONS:
            cur.execute(
                "INSERT INTO mcq_options (interaction_id, label, text, is_correct, char_len) "
                "VALUES (%s,%s,%s,%s,%s)",
                (INTERACTION_ID, label, text, is_correct, len(text)),
            )
        for level, text in HINTS:
            cur.execute(
                "INSERT INTO hints (interaction_id, level, text_md) VALUES (%s,%s,%s)",
                (INTERACTION_ID, level, text),
            )
    print("seed: inserted MCP definition MCQ")


if __name__ == "__main__":
    seed()
