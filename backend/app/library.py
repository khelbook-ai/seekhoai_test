"""Content-reuse library (spec 05 §11). Every built subtopic is registered here with its
generated interactions, diagrams and searchable metadata. When a later course scouts a
similar subtopic (same normalized name + domain), the pipeline can REUSE that content —
cloning the persisted interactions/diagrams instead of re-generating — which skips the most
expensive part of a build (generation + checking + verification) entirely.

Diagrams/illustrations are stored with metadata (kind, caption, keywords) so figures are
easy to find and reuse too.
"""
from __future__ import annotations

import json
import re

from app.db import execute, fetchall, fetchone


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def register_subtopic(course_id: str, st: dict, domain: str, currency_mode: str, package: dict) -> None:
    """Register a freshly-built subtopic in the reuse library with searchable keywords."""
    sid = st["subtopic_id"]
    counts = fetchone(
        """SELECT count(*) FILTER (WHERE type='mcq') mcq, count(*) FILTER (WHERE type='qa') qa
           FROM interactions WHERE subtopic_id=%s AND role='main'""", (sid,)) or {}
    ill = fetchone("SELECT count(*) n FROM diagrams d JOIN interactions i ON d.interaction_id=i.id "
                   "WHERE i.subtopic_id=%s", (sid,))["n"]
    cm = package.get("coverage_map", {}) or {}
    concepts = list(cm.get("required_concepts", []) or []) + list(cm.get("covered_concepts", []) or [])
    defs = [d.get("term") for d in (package.get("extracted", {}) or {}).get("definitions", []) if d.get("term")]
    keywords = sorted({normalize(k) for k in (concepts + defs) if k})[:40]
    execute(
        """INSERT INTO content_library
             (subtopic_name, subtopic_norm, topic_norm, domain, currency_mode,
              source_subtopic_id, source_course_id, dl, mcq_count, qa_count,
              illustration_count, keywords)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (st["name"], normalize(st["name"]), normalize(st.get("topic_name", "")), (domain or "general").lower(),
         currency_mode, sid, course_id, package.get("_dl", 2),
         counts.get("mcq", 0), counts.get("qa", 0), ill, json.dumps(keywords)),
    )


def find_reusable(course_id: str, subtopic_name: str, domain: str,
                  required_concepts: list[str] | None = None) -> str | None:
    """After scouting, check whether an existing library entry can be reused (spec 05 §11).
    Conservative match: same normalized subtopic name + same domain, from a DIFFERENT course,
    that still has content. Returns the source subtopic_id or None."""
    norm = normalize(subtopic_name)
    dom = (domain or "general").lower()
    cands = fetchall(
        """SELECT source_subtopic_id, keywords FROM content_library
           WHERE subtopic_norm = %s AND domain = %s AND source_course_id <> %s
           ORDER BY created_at DESC LIMIT 5""", (norm, dom, course_id))
    req = {normalize(c) for c in (required_concepts or []) if c}
    for c in cands:
        src = c["source_subtopic_id"]
        if not src:
            continue
        has = fetchone("SELECT count(*) n FROM interactions WHERE subtopic_id=%s", (src,))["n"]
        if not has:
            continue
        # if we have scouted concepts, require some overlap so we don't reuse a same-named but
        # differently-scoped subtopic; otherwise the exact name+domain match is enough.
        if req:
            kw = set(c["keywords"] or [])
            if kw and not (req & kw):
                continue
        return str(src)
    return None


def clone_into(target_subtopic_id: str, source_subtopic_id: str) -> dict:
    """Copy all persisted content from a library subtopic into the target subtopic: every
    interaction (main + follow-ups) with its options, hints and diagram, plus the reserve and
    sources. New ids are minted; `reused_from` records provenance."""
    src_inters = fetchall(
        """SELECT id, type, role, dl, ordinal, question_md, diagram_ref, content_panel_md,
                  qa_rubric, answer_key, gen_model, gen_latency_ms, gen_tokens_in, gen_tokens_out
           FROM interactions WHERE subtopic_id=%s ORDER BY role, ordinal""", (source_subtopic_id,))
    n = 0
    for it in src_inters:
        new = execute(
            """INSERT INTO interactions
                 (subtopic_id, type, role, dl, ordinal, question_md, diagram_ref, content_panel_md,
                  qa_rubric, answer_key, gen_model, gen_latency_ms, gen_tokens_in, gen_tokens_out, reused_from)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (target_subtopic_id, it["type"], it["role"], it["dl"], it["ordinal"], it["question_md"],
             it["diagram_ref"], it["content_panel_md"],
             json.dumps(it["qa_rubric"]) if it["qa_rubric"] else None, it["answer_key"],
             it["gen_model"], it["gen_latency_ms"], it["gen_tokens_in"], it["gen_tokens_out"], it["id"]),
        )
        new_id = str(new["id"])
        for o in fetchall("SELECT label, text, is_correct, char_len FROM mcq_options WHERE interaction_id=%s",
                          (it["id"],)):
            execute("INSERT INTO mcq_options (interaction_id, label, text, is_correct, char_len) "
                    "VALUES (%s,%s,%s,%s,%s)", (new_id, o["label"], o["text"], o["is_correct"], o["char_len"]))
        for h in fetchall("SELECT level, text_md FROM hints WHERE interaction_id=%s", (it["id"],)):
            execute("INSERT INTO hints (interaction_id, level, text_md) VALUES (%s,%s,%s)",
                    (new_id, h["level"], h["text_md"]))
        for d in fetchall("SELECT blob_id, provenance, source_url, license_hint, kind, caption, keywords, "
                          "subtopic_name FROM diagrams WHERE interaction_id=%s", (it["id"],)):
            execute("""INSERT INTO diagrams (interaction_id, blob_id, provenance, source_url, license_hint,
                         kind, caption, keywords, subtopic_name)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (new_id, d["blob_id"], d["provenance"], d["source_url"], d["license_hint"],
                     d["kind"], d["caption"], json.dumps(d["keywords"]) if d["keywords"] else None,
                     d["subtopic_name"]))
        n += 1
    # copy reserve + sources so runtime follow-ups and the population UI still work
    res = fetchone("SELECT reserve FROM subtopics WHERE id=%s", (source_subtopic_id,))
    if res and res["reserve"]:
        execute("UPDATE subtopics SET reserve=%s WHERE id=%s",
                (json.dumps(res["reserve"]), target_subtopic_id))
    for s in fetchall("SELECT url, type, title, published, license_hint, meta FROM sources WHERE subtopic_id=%s",
                      (source_subtopic_id,)):
        execute("""INSERT INTO sources (subtopic_id, url, type, title, published, license_hint, scraped_at, meta)
                   VALUES (%s,%s,%s,%s,%s,%s, now(), %s)""",
                (target_subtopic_id, s["url"], s["type"], s["title"], s["published"], s["license_hint"],
                 json.dumps(s["meta"]) if s["meta"] else None))
    return {"interactions": n}
