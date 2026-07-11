"""Content pipeline (spec 05, 02 §2). For each subtopic: scout → audit (scout-again
loop) → generate → option/domain/verification checks (regen loop) → persist → then
cost reconciliation. Generators read ONLY the Content Package (no re-scraping).

Runs in a background task after cost approval (app.build.run_build). Idempotent per
course: skips subtopics that already have interactions so a re-run resumes.
"""
from __future__ import annotations

import json

from app.agents import auditor, cost_reconciliation, scout
from app.agents.checkers import option, semantic
from app.agents.generators import content as gen
from app.blobstore import get_blobstore
from app.config import get_settings
from app.db import execute, fetchone
from app.mcp import tools
from app.store import get_course, list_subtopics


# --- persistence -------------------------------------------------------------
def _persist_sources(subtopic_id: str, package: dict) -> None:
    for s in package.get("sources", []):
        execute(
            """INSERT INTO sources (subtopic_id, url, type, title, published, license_hint, scraped_at, meta)
               VALUES (%s,%s,%s,%s,%s,%s, now(), %s)""",
            (subtopic_id, s.get("url"), s.get("type"), s.get("title"),
             s.get("published") or None, s.get("license_hint"),
             json.dumps({"source_id": s.get("source_id")})),
        )


def _persist_interaction(subtopic_id: str, ordinal: int, item: dict,
                         checks: list[tuple], package: dict) -> str:
    gen_meta = item.get("_gen", {})
    row = execute(
        """INSERT INTO interactions
             (subtopic_id, type, dl, ordinal, question_md, content_panel_md, qa_rubric,
              answer_key, gen_model, gen_latency_ms, gen_tokens_in, gen_tokens_out)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (subtopic_id, item["_type"], item["_dl"], ordinal, item.get("question_md"),
         item.get("content_panel_md"),
         json.dumps(item.get("qa_rubric")) if item.get("qa_rubric") else None,
         item.get("answer_key"), gen_meta.get("model"), gen_meta.get("latency_ms"),
         gen_meta.get("tin"), gen_meta.get("tout")),
    )
    interaction_id = str(row["id"])

    if item["_type"] == "mcq":
        for o in item.get("options", []):
            execute(
                "INSERT INTO mcq_options (interaction_id, label, text, is_correct, char_len) "
                "VALUES (%s,%s,%s,%s,%s)",
                (interaction_id, o.get("label"), o.get("text"), bool(o.get("is_correct")),
                 len(o.get("text") or "")),
            )
    for lvl, htext in enumerate(item.get("hints", [])[:3], start=1):
        execute("INSERT INTO hints (interaction_id, level, text_md) VALUES (%s,%s,%s)",
                (interaction_id, lvl, htext))

    for checker, verdict in checks:
        v = "pass"
        issues = verdict
        if checker == "domain":
            v = "pass" if verdict.get("on_domain", True) else "fail"
        elif checker == "verification":
            v = verdict.get("verdict", "pass")
        elif checker == "option":
            v = "fail" if verdict else "pass"
        execute(
            "INSERT INTO check_runs (interaction_id, checker, verdict, issues, model) "
            "VALUES (%s,%s,%s,%s,%s)",
            (interaction_id, checker, v, json.dumps(issues), None),
        )

    _attach_diagram(interaction_id, subtopic_id, item, package)
    return interaction_id


def _attach_diagram(interaction_id: str, subtopic_id: str, item: dict, package: dict) -> None:
    sug = item.get("diagram_suggestion") or {}
    if not sug.get("needed"):
        return
    what = sug.get("what") or item.get("question_md", "")[:120]
    figs = package.get("extracted", {}).get("figures", [])
    # prefer a sourced figure with a fetchable image URL
    for f in figs:
        url = f.get("source_url")
        if url and str(url).lower().split("?")[0].endswith((".png", ".jpg", ".jpeg", ".svg", ".webp")):
            fetched = tools.file_fetcher(url)
            if not fetched.get("error"):
                blob_id = fetched["blob_ref"]
                _write_diagram(interaction_id, blob_id, "sourced", url, f.get("license_hint"))
                execute("UPDATE interactions SET diagram_ref = %s WHERE id = %s",
                        (blob_id, interaction_id))
                return
    # else generate an SVG schematic (D8) with provenance recorded
    svg = gen.generate_svg_diagram(what, package.get("subtopic_id", subtopic_id))
    if svg:
        blob_id = get_blobstore().put("diagram", "image/svg+xml", svg.encode("utf-8"))
        _write_diagram(interaction_id, blob_id, "generated", None, None)
        execute("UPDATE interactions SET diagram_ref = %s WHERE id = %s",
                (blob_id, interaction_id))


def _write_diagram(interaction_id: str, blob_id: str, provenance: str,
                   source_url: str | None, license_hint: str | None) -> None:
    execute(
        "INSERT INTO diagrams (interaction_id, blob_id, provenance, source_url, license_hint) "
        "VALUES (%s,%s,%s,%s,%s)",
        (interaction_id, blob_id, provenance, source_url, license_hint),
    )


# --- generation + checks -----------------------------------------------------
def _load_intent(course_id: str) -> tuple[dict, dict]:
    row = fetchone(
        "SELECT ip.orientation, ip.seniority, ip.domain_grounding FROM courses c "
        "JOIN intent_profiles ip ON ip.user_id = c.user_id WHERE c.id = %s "
        "ORDER BY ip.created_at DESC LIMIT 1", (course_id,))
    if not row:
        return {"orientation": "general", "seniority": "mid"}, {"domain": "general", "must_ground": False}
    return ({"orientation": row["orientation"], "seniority": row["seniority"]},
            row["domain_grounding"] or {"domain": "general", "must_ground": False})


def _scout_and_audit(st: dict, currency_mode: str, domain_grounding: dict, since: str | None) -> tuple[dict, dict]:
    cfg = get_settings().section("scouting")
    max_rounds = int(cfg.get("max_scout_rounds", 3))
    package, audit_res, extra = None, {"comprehensive": False, "score": 0.0, "gaps": []}, ""
    for _round in range(max_rounds):
        package = scout.scout_subtopic(st, currency_mode=currency_mode,
                                       domain_grounding=domain_grounding, since=since,
                                       extra_actions=extra)
        audit_res = auditor.audit(package, currency_mode=currency_mode)
        if audit_res.get("comprehensive"):
            break
        acts = audit_res.get("recommended_actions", [])
        extra = "Recommended actions from the auditor: " + json.dumps(acts)[:800]
    return package, audit_res


def _generate_and_check(st: dict, package: dict, intent: dict, domain_grounding: dict,
                        course_id: str) -> list[dict]:
    max_retries = int(get_settings().section("checkers").get("max_regen_retries", 2))
    specs = gen.plan_interactions(package)
    results: list[dict] = []

    for spec in specs:
        item = None
        checks: list[tuple] = []
        flagged = False
        for attempt in range(max_retries + 1):
            if spec["kind"] == "mcq":
                item = gen.generate_mcq(st, package, intent, spec["dl"],
                                        definition=spec["definition"], course_id=course_id)
            else:
                item = gen.generate_qa(st, package, intent, spec["dl"], course_id=course_id)

            dom = semantic.domain_check(item, st, domain_grounding, course_id)
            if not dom.get("on_domain", True) and attempt < max_retries:
                st = {**st, "description": st["description"] + " | fix: " + (dom.get("regen_hint") or "")}
                continue
            ver = semantic.verify(item, st, package, course_id)
            checks = [("domain", dom), ("verification", ver)]
            if ver.get("verdict") == "fail" and attempt < max_retries:
                st = {**st, "description": st["description"] + " | fix: " + (ver.get("suggested_fix") or "")}
                continue
            flagged = (not dom.get("on_domain", True)) or (ver.get("verdict") == "fail")
            break
        item["_checks"] = checks
        item["_flagged"] = flagged
        results.append(item)

    # Option Checker across the subtopic's MCQs (deterministic: variety + balance)
    mcqs = [it for it in results if it["_type"] == "mcq"]
    opt = option.check_and_fix(mcqs)
    for it in mcqs:
        it["_checks"] = it.get("_checks", []) + [("option", opt["violations"])]
    return results


# --- top-level ---------------------------------------------------------------
def run_content_pipeline(course_id: str) -> None:
    course = get_course(course_id)
    currency_mode = course["currency_mode"]
    since = None
    if currency_mode == "latest_research":
        from datetime import date, timedelta

        since = (date.today() - timedelta(days=365)).isoformat()

    intent, domain_grounding = _load_intent(course_id)
    subtopics = list_subtopics(course_id)

    for st in subtopics:
        st = dict(st)
        st["subtopic_id"] = str(st["subtopic_id"])
        st["course_id"] = course_id
        # idempotent resume: skip if this subtopic already has interactions
        existing = fetchone("SELECT count(*) AS n FROM interactions WHERE subtopic_id = %s",
                            (st["subtopic_id"],))
        if existing and existing["n"] > 0:
            continue

        package, audit_res = _scout_and_audit(st, currency_mode, domain_grounding, since)
        _persist_sources(st["subtopic_id"], package)
        execute(
            "UPDATE subtopics SET partially_sourced = %s, audit_score = %s, audit_gaps = %s, "
            "source_manifest = %s WHERE id = %s",
            (not audit_res.get("comprehensive"), audit_res.get("score"),
             json.dumps(audit_res.get("gaps", [])),
             json.dumps(package.get("sources", [])), st["subtopic_id"]),
        )

        items = _generate_and_check(st, package, intent, domain_grounding, course_id)
        for ordinal, item in enumerate(items):
            _persist_interaction(st["subtopic_id"], ordinal, item, item.get("_checks", []), package)

    cost_reconciliation.reconcile(course_id, notes="build complete")
