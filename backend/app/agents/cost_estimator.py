"""Cost Estimator (spec 03 §6). Deterministic token/price math over the curriculum,
priced from models.yaml, with a contingency buffer. Gates the build at cost_gate.

Method: per subtopic, target_question_count items × (avg tokens per MCQ + Q&A + hints +
content panel + diagram handling) × (generation + 3 checkers + verification passes) +
scouting overhead. Multiply by per-model prices; add buffer (default 15%).
"""
from __future__ import annotations

from app import cost_history
from app.config import get_settings
from app.registry import get_model
from app.schemas import CostEstimate, Curriculum

# Heuristic average tokens per unit of work (input+output combined), tuned conservatively.
_AVG = {
    "gen_per_item_in": 1500, "gen_per_item_out": 1200,   # content+mcq+qa+hints+diagram gen
    "checker_per_item_in": 900, "checker_per_item_out": 300,  # each of option/domain/verify
    "scout_per_subtopic_in": 2500, "scout_per_subtopic_out": 1500,
    "audit_per_subtopic_in": 3000, "audit_per_subtopic_out": 600,
}


def _completion_minutes(curriculum: Curriculum, orientation: str = "general") -> int:
    """Rough learner time-to-complete from the curriculum (before the course is built).
    Each scored item ~1.3 min; technical learners also get a code walkthrough per subtopic."""
    ct = get_settings().section("completion_time")
    per_item = (float(ct.get("mcq", 1.0)) + float(ct.get("order", 1.5))
                + float(ct.get("blanks", 1.5)) + float(ct.get("dragdrop", 2.0))) / 4.0
    allowance = 1 + float(ct.get("followup_allowance", 0.4)) * float(ct.get("qa", 2.5)) / max(per_item, 0.1) * 0.25
    minutes = 0.0
    for topic in curriculum.topics:
        for st in topic.subtopics:
            minutes += max(1, int(st.target_question_count)) * per_item
            if orientation == "technical":
                minutes += float(ct.get("walkthrough", 4.0)) + float(ct.get("mcq", 1.0))
    return int(round(minutes * allowance))


def estimate(curriculum: Curriculum, currency_mode: str = "fundamentals",
             domain: str | None = None, orientation: str = "general") -> CostEstimate:
    cfg = get_settings().section("cost")
    buffer_pct = int(cfg.get("buffer_pct", 15))

    gen = get_model("content_generator")
    opt = get_model("option_checker")
    dom = get_model("domain_checker")
    ver = get_model("content_verification")
    scout = get_model("course_scout")
    audit = get_model("scouting_auditor")

    by_phase = {"scouting": 0.0, "generation": 0.0, "checking": 0.0, "verification": 0.0}
    by_subtopic: list[dict] = []
    tokens_total = 0
    recency_mult = 1.3 if currency_mode == "latest_research" else 1.0

    for topic in curriculum.topics:
        for st in topic.subtopics:
            q = max(1, int(st.target_question_count))

            # scouting + audit (per subtopic)
            s_in = _AVG["scout_per_subtopic_in"] * recency_mult
            s_out = _AVG["scout_per_subtopic_out"] * recency_mult
            a_in, a_out = _AVG["audit_per_subtopic_in"], _AVG["audit_per_subtopic_out"]
            scout_cost = scout.cost(s_in, s_out) + audit.cost(a_in, a_out)

            # generation (per item)
            g_cost = q * gen.cost(_AVG["gen_per_item_in"], _AVG["gen_per_item_out"])

            # checking: option + domain per item (verification counted separately)
            chk_cost = q * (opt.cost(_AVG["checker_per_item_in"], _AVG["checker_per_item_out"])
                            + dom.cost(_AVG["checker_per_item_in"], _AVG["checker_per_item_out"]))

            # verification (Gemini) per item
            ver_cost = q * ver.cost(_AVG["checker_per_item_in"], _AVG["checker_per_item_out"])

            by_phase["scouting"] += scout_cost
            by_phase["generation"] += g_cost
            by_phase["checking"] += chk_cost
            by_phase["verification"] += ver_cost

            tokens_total += int((s_in + s_out + a_in + a_out)
                                + q * (_AVG["gen_per_item_in"] + _AVG["gen_per_item_out"])
                                + q * 3 * (_AVG["checker_per_item_in"] + _AVG["checker_per_item_out"]))
            sub_est = round(scout_cost + g_cost + chk_cost + ver_cost, 5)
            by_subtopic.append({"subtopic": st.name, "estimate": sub_est,
                                "target_question_count": q})

    raw_total = round(sum(by_phase.values()) * (1 + buffer_pct / 100), 4)
    by_phase = {k: round(v, 5) for k, v in by_phase.items()}

    assumptions = [
        f"~{_AVG['gen_per_item_in'] + _AVG['gen_per_item_out']} tokens/item generation, "
        "option+domain+verification checks each, 0 regens assumed",
        f"scouting+audit per subtopic; recency multiplier {recency_mult}x",
        f"{buffer_pct}% contingency buffer applied",
    ]

    # History calibration (spec 03 §6, 06 §5): correct the raw heuristic estimate by how
    # estimates actually panned out for SIMILAR past courses. Only similar courses are used.
    sub_names = [st.name for t in curriculum.topics for st in t.subtopics]
    kw = cost_history.signature(curriculum.title, sub_names, domain)
    calib = cost_history.calibration(kw, currency_mode)
    total = raw_total
    if calib:
        total = round(raw_total * calib["factor"], 4)
        assumptions.append(
            f"calibrated ×{calib['factor']} from {calib['samples']} similar past course(s) "
            f"(their actual ran {calib['factor']}× the heuristic estimate)")

    return CostEstimate(
        currency="USD", total_estimate=total, raw_estimate=raw_total, buffer_pct=buffer_pct,
        by_phase=by_phase, by_subtopic=by_subtopic, tokens_estimate=tokens_total,
        calibration=calib, est_completion_minutes=_completion_minutes(curriculum, orientation),
        assumptions=assumptions,
    )
