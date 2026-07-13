"""Course-scoped RAG study assistant (spec 04 §12). Answers a learner's free-text question using
ONLY the persisted knowledge base of the course they're currently in — never the web, never
another course. Retrieval is a lightweight in-process TF-IDF over the course's own content (no
tokens spent); a single fast-model call then synthesises a short, grounded answer.

Both ends are hard-capped to keep this cheap on the learner's path: query ≤ 300 chars,
answer ≤ 400 chars. Reads persisted content only — like the runtime, it never regenerates
course content (06 §6).
"""
from __future__ import annotations

import json
import math
import re

from app.db import execute, fetchall, fetchone
from app.llm import complete_text
from app.prompts import render

QUERY_MAX = 300     # keep the learner's question short (UI enforces; backed up here)
ANSWER_MAX = 2000   # generous backstop only — the assistant answers for quality, not token-cost
TOP_K = 5           # retrieved passages fed to the model
_CHUNK_CHARS = 500  # per-passage truncation before it enters the prompt

_STOP = {"the", "a", "an", "of", "and", "or", "to", "in", "for", "with", "on", "is", "are",
         "was", "were", "be", "by", "as", "at", "it", "this", "that", "these", "those", "how",
         "what", "why", "when", "which", "who", "does", "do", "can", "will", "from", "into"}


def _tok(s: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if len(t) > 2 and t not in _STOP]


def _model_answer(rubric) -> str | None:
    if isinstance(rubric, str):
        try:
            rubric = json.loads(rubric)
        except (ValueError, TypeError):
            return None
    return rubric.get("model_answer") if isinstance(rubric, dict) else None


def build_corpus(course_id: str) -> list[dict]:
    """Assemble this course's knowledge base as retrievable chunks (persisted content only)."""
    chunks: list[dict] = []
    for r in fetchall(
        "SELECT s.name, s.description FROM subtopics s JOIN topics t ON s.topic_id = t.id "
        "WHERE t.course_id = %s", (course_id,)):
        text = f"{r['name']}. {r['description'] or ''}".strip()
        if len(text) > 3:
            chunks.append({"ref": r["name"], "text": text})
    for r in fetchall(
        """SELECT i.id, i.question_md, i.content_panel_md, i.qa_rubric, s.name subtopic
           FROM interactions i JOIN subtopics s ON i.subtopic_id = s.id
           JOIN topics t ON s.topic_id = t.id WHERE t.course_id = %s""", (course_id,)):
        if r["content_panel_md"]:
            chunks.append({"ref": r["subtopic"], "text": r["content_panel_md"]})
        ma = _model_answer(r["qa_rubric"])
        if ma:
            q = (r["question_md"] or "").strip()
            chunks.append({"ref": r["subtopic"], "text": f"{q} {ma}".strip()})
        # The correct MCQ option is a compact, factual statement about the concept — high-signal
        # material to ground answers in — so index it alongside its question.
        opts = fetchall(
            "SELECT text, is_correct FROM mcq_options WHERE interaction_id = %s", (r["id"],))
        correct = " ".join(o["text"] for o in opts if o["is_correct"] and o["text"])
        if correct:
            q = (r["question_md"] or "").strip()
            chunks.append({"ref": r["subtopic"], "text": f"{q} {correct}".strip()})
    return chunks


_BM25_K1 = 1.5
_BM25_B = 0.75


def retrieve(chunks: list[dict], query: str, k: int = TOP_K) -> list[dict]:
    """Rank course chunks for the query with BM25, then run a **term-coverage** pass so that any
    query term actually present in the course is represented in the result — even a rare one the
    learner is really asking about (e.g. "langgraph"). Without this, a chunk matching several
    common query words outscores the single chunk that holds the rare term, and the assistant
    would wrongly conclude the course "doesn't cover" it. Pure Python; spends no tokens.
    """
    qterms = list(dict.fromkeys(_tok(query)))     # unique, order-preserving
    if not qterms or not chunks:
        return []
    docs = [_tok(c["text"]) for c in chunks]
    n = len(docs)
    lengths = [len(d) or 1 for d in docs]
    avgdl = sum(lengths) / n
    df: dict[str, int] = {}
    tfs: list[dict[str, int]] = []
    for d in docs:
        tf: dict[str, int] = {}
        for term in d:
            tf[term] = tf.get(term, 0) + 1
        tfs.append(tf)
        for term in tf:
            df[term] = df.get(term, 0) + 1

    def idf(t: str) -> float:
        c = df.get(t, 0)
        return math.log(1 + (n - c + 0.5) / (c + 0.5)) if c else 0.0

    def score(i: int) -> float:
        tf, L = tfs[i], lengths[i]
        s = 0.0
        for t in qterms:
            f = tf.get(t, 0)
            if f:
                s += idf(t) * (f * (_BM25_K1 + 1)) / (f + _BM25_K1 * (1 - _BM25_B + _BM25_B * L / avgdl))
        return s

    ranked = sorted(((score(i), i) for i in range(n)), reverse=True)
    selected = [i for sc, i in ranked if sc > 0][:k]
    chosen = set(selected)
    covered = set().union(*(set(docs[i]) & set(qterms) for i in selected)) if selected else set()

    # Coverage: ensure each *discriminating* query term that exists in the course is represented.
    cap = k + 3
    for t in qterms:
        if len(selected) >= cap:
            break
        if t in covered or df.get(t, 0) == 0 or df.get(t, 0) > 0.5 * n:
            continue  # already covered / absent from course / too common to matter
        best = next((i for _, i in ranked if i not in chosen and tfs[i].get(t, 0)), None)
        if best is not None:
            selected.append(best)
            chosen.add(best)
            covered |= set(docs[best]) & set(qterms)
    return [chunks[i] for i in selected]


def answer(course_id: str, query: str, *, user_id: str | None = None,
           session_id: str | None = None) -> dict:
    """Check the course material, then let the model give the best answer it can — grounded in the
    course where possible, supplementing with its own knowledge when that helps (spec 04 §9). The
    exchange is persisted so the assistant's history survives a refresh and spans all the learner's
    courses."""
    query = (query or "").strip()[:QUERY_MAX]
    hits = retrieve(build_corpus(course_id), query)
    if hits:
        context = "\n\n".join(f"[{i + 1}] {c['text'][:_CHUNK_CHARS]}" for i, c in enumerate(hits))
    else:
        context = ("(No passage from this course's material matched this question. Answer from your "
                   "own knowledge and make clear it goes beyond what the course covers.)")
    try:
        res = complete_text(
            "course_chat", "You are a knowledgeable, accurate study assistant.",
            render("course_chat", context=context, question=query),
            phase="chat", max_tokens=800, temperature=0.3, course_id=course_id)
        ans = res.text.strip()[:ANSWER_MAX]
    except Exception:
        ans = "Sorry — I couldn't answer that right now. Please try again."
    # de-duplicate the retrieved subtopic names for a light "consulted" citation
    seen: list[str] = []
    for c in hits:
        if c["ref"] not in seen and c["ref"] != "source":
            seen.append(c["ref"])
    ans = ans or "Sorry — I couldn't produce an answer for that."
    saved = _persist(user_id, course_id, session_id, query, ans, bool(hits), seen[:3])
    return {"answer": ans, "grounded": bool(hits), "sources": seen[:3], **saved}


def _persist(user_id, course_id, session_id, question, answer_text, grounded, sources) -> dict:
    """Store one Q&A exchange and echo back the fields the UI needs (id, timestamp, course name)."""
    try:
        row = execute(
            """INSERT INTO assistant_messages
                 (user_id, course_id, session_id, question, answer, grounded, sources)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id, created_at""",
            (user_id, course_id, session_id, question, answer_text, grounded, json.dumps(sources)))
        c = fetchone("SELECT title FROM courses WHERE id = %s", (course_id,))
        return {"id": str(row["id"]), "created_at": row["created_at"].isoformat(),
                "course_name": c["title"] if c else None}
    except Exception:
        return {}


def history(user_id: str, limit: int = 300) -> list[dict]:
    """The learner's whole assistant conversation, oldest first, across ALL their courses — each
    exchange tagged with the course it was asked in and a timestamp (spec 06 §10)."""
    rows = fetchall(
        """SELECT m.id, m.course_id, c.title course_name, m.question, m.answer, m.grounded,
                  m.sources, m.created_at
           FROM assistant_messages m LEFT JOIN courses c ON m.course_id = c.id
           WHERE m.user_id = %s ORDER BY m.created_at LIMIT %s""",
        (user_id, limit))
    return [{"id": str(r["id"]), "course_id": str(r["course_id"]) if r["course_id"] else None,
             "course_name": r["course_name"], "question": r["question"], "answer": r["answer"],
             "grounded": r["grounded"], "sources": r["sources"] or [],
             "created_at": r["created_at"].isoformat() if r["created_at"] else None}
            for r in rows]
