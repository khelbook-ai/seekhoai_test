"""Content pipeline (spec 05, 02 §2). For each subtopic: scout → audit (scout-again
loop) → generate → option/domain/verification checks (regen loop) → persist → then
cost reconciliation. Generators read ONLY the Content Package (no re-scraping).

Runs in a background task after cost approval (app.build.run_build). Idempotent per
course: skips subtopics that already have interactions so a re-run resumes.
"""
from __future__ import annotations

import json

from app import events
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
                         checks: list[tuple], package: dict, role: str = "main") -> str:
    gen_meta = item.get("_gen", {})
    answer_key = item.get("answer_key")
    if item["_type"] == "mcq" and not answer_key:
        # HARD invariant (spec 06 §7): an MCQ must never persist a null answer_key, or the
        # runtime shows "the answer was null". Fall back to the flagged-correct option, else A.
        answer_key = next((o.get("label") for o in item.get("options", []) if o.get("is_correct")), None) or "A"
    row = execute(
        """INSERT INTO interactions
             (subtopic_id, type, role, dl, ordinal, question_md, content_panel_md, qa_rubric,
              answer_key, gen_model, gen_latency_ms, gen_tokens_in, gen_tokens_out)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (subtopic_id, item["_type"], role, item["_dl"], ordinal, item.get("question_md"),
         item.get("content_panel_md"),
         json.dumps(item.get("qa_rubric")) if item.get("qa_rubric") else None,
         answer_key, gen_meta.get("model"), gen_meta.get("latency_ms"),
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
    cid = st["course_id"]
    cfg = get_settings().section("scouting")
    max_rounds = int(cfg.get("max_scout_rounds", 3))
    package, audit_res, extra = None, {"comprehensive": False, "score": 0.0, "gaps": []}, ""
    for _round in range(max_rounds):
        events.emit(cid, "scouting", "round", f"scout round {_round + 1}/{max_rounds} for '{st['name']}'")
        package = scout.scout_subtopic(st, currency_mode=currency_mode,
                                       domain_grounding=domain_grounding, since=since,
                                       extra_actions=extra)
        events.emit(cid, "scouting", "audit", "Scouting Auditor (Claude Sonnet) reviewing Content Package…")
        audit_res = auditor.audit(package, currency_mode=currency_mode)
        events.emit(cid, "scouting", "audit",
                    f"  ↳ score {audit_res.get('score')} · comprehensive={audit_res.get('comprehensive')}"
                    + (f" · gaps: {'; '.join(audit_res.get('gaps', [])[:2])}" if not audit_res.get("comprehensive") else ""))
        if audit_res.get("comprehensive"):
            break
        acts = audit_res.get("recommended_actions", [])
        extra = "Recommended actions from the auditor: " + json.dumps(acts)[:800]
    return package, audit_res


def _one_interaction(spec: dict, st: dict, package: dict, intent: dict,
                     domain_grounding: dict, course_id: str, max_retries: int) -> dict:
    """Generate ONE interaction and run its full generate→domain-check→verify chain (with
    regen). Self-contained and independent of sibling interactions: it works on a private
    copy of the subtopic context, so a regen 'fix' hint here can never leak into another
    interaction — parallel siblings stay aligned because each sees identical inputs."""
    st = dict(st)                        # private copy — no cross-interaction bleed
    item: dict = {}
    checks: list[tuple] = []
    flagged = False
    for attempt in range(max_retries + 1):
        label = f"{spec['kind'].upper()}{' (definition)' if spec.get('definition') else ''} DL{spec['dl']}"
        events.emit(course_id, "generation", "generate",
                    f"generating {label} for '{st['name']}'" + (f" (regen {attempt})" if attempt else ""))
        if spec["kind"] == "mcq":
            item = gen.generate_mcq(st, package, intent, spec["dl"],
                                    definition=spec["definition"], course_id=course_id)
        else:
            item = gen.generate_qa(st, package, intent, spec["dl"], course_id=course_id)

        events.emit(course_id, "checking", "check", "Domain Checker (GLM) reviewing framing…")
        dom = semantic.domain_check(item, st, domain_grounding, course_id)
        if not dom.get("on_domain", True) and attempt < max_retries:
            events.emit(course_id, "checking", "check", f"  ↳ off-domain → regen ({dom.get('reason','')[:40]})")
            st = {**st, "description": st["description"] + " | fix: " + (dom.get("regen_hint") or "")}
            continue
        events.emit(course_id, "verification", "verify", "Verification (Gemini, independent) checking accuracy…")
        ver = semantic.verify(item, st, package, course_id)
        checks = [("domain", dom), ("verification", ver)]
        if ver.get("verdict") == "fail" and attempt < max_retries:
            events.emit(course_id, "verification", "verify", f"  ↳ failed → regen ({'; '.join(ver.get('issues', [])[:1])[:40]})")
            st = {**st, "description": st["description"] + " | fix: " + (ver.get("suggested_fix") or "")}
            continue
        flagged = (not dom.get("on_domain", True)) or (ver.get("verdict") == "fail")
        events.emit(course_id, "verification", "verify",
                    f"  ↳ {label}: domain={'ok' if dom.get('on_domain', True) else 'FAIL'} "
                    f"verify={ver.get('verdict', 'pass')}" + (" · FLAGGED for review" if flagged else ""))
        break
    item["_checks"] = checks
    item["_flagged"] = flagged
    return item


def _generate_and_check(st: dict, package: dict, intent: dict, domain_grounding: dict,
                        course_id: str) -> list[dict]:
    max_retries = int(get_settings().section("checkers").get("max_regen_retries", 2))
    n_par = max(1, int(get_settings().section("build").get("max_concurrent_interactions", 4)))
    specs = gen.plan_interactions(package)

    # Interactions within a subtopic are independent (each has its own generate→check→verify
    # chain over the SAME read-only package), so build them concurrently. Order is preserved
    # so the definition MCQ stays first (ordinal 0). The global LLM gate caps total load.
    results: list[dict] = [None] * len(specs)  # type: ignore[list-item]
    if n_par == 1 or len(specs) <= 1:
        for i, spec in enumerate(specs):
            results[i] = _one_interaction(spec, st, package, intent, domain_grounding, course_id, max_retries)
    else:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=min(n_par, len(specs)),
                                thread_name_prefix="interaction") as pool:
            futs = {pool.submit(_one_interaction, spec, st, package, intent, domain_grounding,
                                course_id, max_retries): i for i, spec in enumerate(specs)}
            for fut, i in futs.items():
                results[i] = fut.result()

    # Option Checker across the subtopic's MCQs (deterministic: variety + balance)
    mcqs = [it for it in results if it["_type"] == "mcq"]
    opt = option.check_and_fix(mcqs)
    for it in mcqs:
        it["_checks"] = it.get("_checks", []) + [("option", opt["violations"])]
    return results


# --- follow-up reserve (spec 04 §4, 05 §10) ----------------------------------
def _build_followups(st: dict, package: dict, intent: dict, domain_grounding: dict,
                     course_id: str) -> None:
    """Build the subtopic's runtime reserve and pre-generate its seed follow-up Q&A."""
    from app.agents.generators import followup

    st_ctx = {**st, "calibrated_dl": package.get("_dl", 2), "domain_grounding": domain_grounding}
    reserve = followup.build_reserve(st_ctx, package, intent, domain_grounding, course_id)
    execute("UPDATE subtopics SET reserve = %s WHERE id = %s",
            (json.dumps(reserve), st["subtopic_id"]))
    try:
        seed = followup.generate_seed_followup(st_ctx, package, reserve, intent,
                                               int(package.get("_dl", 2)), course_id)
        _persist_interaction(st["subtopic_id"], 0, seed, [], package, role="followup_seed")
        events.emit(course_id, "persist", "persist", f"  ↳ seed follow-up Q&A ready for '{st['name']}'")
    except Exception as e:
        events.emit(course_id, "generation", "warn", f"  ↳ seed follow-up failed ({str(e)[:50]})")


# --- per-subtopic worker (runs concurrently, spec 02 §5) ---------------------
def _build_subtopic(course_id: str, st: dict, si: int, total: int, currency_mode: str,
                    domain_grounding: dict, intent: dict, since: str | None) -> None:
    """Scout → audit → generate → check → persist → reserve for ONE subtopic. Self-contained
    so subtopics can run in parallel: all DB access goes through the thread-safe pool and
    build events key by course_id, so concurrent logs simply interleave."""
    st = dict(st)
    st["subtopic_id"] = str(st["subtopic_id"])
    st["course_id"] = course_id
    # idempotent resume: skip if this subtopic already has interactions
    existing = fetchone("SELECT count(*) AS n FROM interactions WHERE subtopic_id = %s",
                        (st["subtopic_id"],))
    if existing and existing["n"] > 0:
        events.emit(course_id, "generation", "skip", f"[{si}/{total}] '{st['name']}' already built — skipping")
        return

    events.emit(course_id, "scouting", "subtopic", f"── [{si}/{total}] subtopic: {st['name']} ──")
    package, audit_res = _scout_and_audit(st, currency_mode, domain_grounding, since)
    _persist_sources(st["subtopic_id"], package)
    if not audit_res.get("comprehensive"):
        events.emit(course_id, "scouting", "warn",
                    f"'{st['name']}' marked PARTIALLY SOURCED after {get_settings().section('scouting').get('max_scout_rounds', 3)} rounds")
    execute(
        "UPDATE subtopics SET partially_sourced = %s, audit_score = %s, audit_gaps = %s, "
        "source_manifest = %s WHERE id = %s",
        (not audit_res.get("comprehensive"), audit_res.get("score"),
         json.dumps(audit_res.get("gaps", [])),
         json.dumps(package.get("sources", [])), st["subtopic_id"]),
    )

    items = _generate_and_check(st, package, intent, domain_grounding, course_id)
    events.emit(course_id, "generation", "option_check",
                f"Option Checker: {sum(1 for i in items if i['_type']=='mcq')} MCQs — answer-position variety + length balance")
    for ordinal, item in enumerate(items):
        _persist_interaction(st["subtopic_id"], ordinal, item, item.get("_checks", []), package)
    events.emit(course_id, "persist", "persist",
                f"persisted {len(items)} interactions for '{st['name']}'")

    # Weakness Remediation Reserve + pre-generated seed follow-up (spec 04 §4, 05 §10).
    # A learner reaches Q&A only after a wrong MCQ; the first follow-up is pre-built and
    # the reserve backs runtime root-cause probes so we never scrape mid-session.
    _build_followups(st, package, intent, domain_grounding, course_id)


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
    total = len(subtopics)

    # Subtopics are independent, so build them with bounded concurrency (spec 02 §5). The
    # pool is capped so we don't overwhelm provider rate limits or the DB connection pool.
    max_workers = max(1, int(get_settings().section("build").get("max_concurrent_subtopics", 4)))
    max_workers = min(max_workers, total or 1, 8)  # keep under the DB pool (max_size=10)
    events.emit(course_id, "generation", "start",
                f"build started · {total} subtopics · up to {max_workers} in parallel · "
                f"currency={currency_mode} · domain='{domain_grounding.get('domain', 'general')}'")

    if max_workers == 1:
        for si, st in enumerate(subtopics, start=1):
            _build_subtopic(course_id, st, si, total, currency_mode, domain_grounding, intent, since)
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        failures = 0
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="subtopic") as pool:
            futs = {pool.submit(_build_subtopic, course_id, st, si, total, currency_mode,
                                domain_grounding, intent, since): st
                    for si, st in enumerate(subtopics, start=1)}
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:  # one subtopic failing must not abort the whole build
                    failures += 1
                    events.emit(course_id, "generation", "warn",
                                f"subtopic '{futs[fut]['name']}' failed: {str(e)[:80]}")
        if failures and failures == total:
            raise RuntimeError("all subtopics failed to build")

    events.emit(course_id, "cost", "reconcile", "Cost Reconciliation: actual vs estimate…")
    recon = cost_reconciliation.reconcile(course_id, notes="build complete")
    events.emit(course_id, "cost", "reconcile",
                f"  ↳ actual ${recon['actual']:.4f} vs est ${recon['estimated']:.4f} ({recon['delta_pct']}%)")
    events.emit(course_id, "persist", "done", "✅ build complete")
