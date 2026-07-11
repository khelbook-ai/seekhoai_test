"""Option Checker (spec 03 §8). Mostly deterministic MCQ structure validation across a
subtopic: exactly 4 options, answer-position variety (reshuffle to near-uniform), and
aggregate length balance (flag if the correct option is systematically longer).

Hard invariant (spec 06 §7): every persisted MCQ has EXACTLY 4 options and a non-null
`answer_key`. Generators sometimes drift (e.g. return 5 options, or forget to flag the
correct one) — this checker REPAIRS that deterministically so a broken item can never
reach the learner with a null answer (the "answer was null" content-feedback bug).
"""
from __future__ import annotations

import random

_LABELS = ["A", "B", "C", "D"]


def _item_ok(mcq: dict) -> list[str]:
    issues = []
    opts = mcq.get("options", [])
    if len(opts) != 4:
        issues.append(f"expected 4 options, got {len(opts)}")
    n_correct = sum(1 for o in opts if o.get("is_correct"))
    if n_correct != 1:
        issues.append(f"expected exactly 1 correct option, got {n_correct}")
    texts = [(o.get("text") or "").strip() for o in opts]
    if len(set(texts)) != len(texts):
        issues.append("duplicate option text (options must be mutually exclusive)")
    return issues


def _coerce_four(mcq: dict) -> None:
    """Force the MCQ to exactly 4 well-formed options with exactly one correct.
    Mutates in place. Deterministic so it never leaves an item unanswerable."""
    opts = [dict(o) for o in mcq.get("options", []) if (o.get("text") or "").strip()]

    # exactly one correct: if the generator flagged none, fall back to answer_key or first
    correct = [o for o in opts if o.get("is_correct")]
    if not correct and opts:
        key = (mcq.get("answer_key") or "").strip().upper()
        picked = next((o for o in opts if (o.get("label") or "").upper() == key), opts[0])
        for o in opts:
            o["is_correct"] = o is picked
    elif len(correct) > 1:
        keep = correct[0]
        for o in opts:
            o["is_correct"] = o is keep

    correct_opt = next((o for o in opts if o.get("is_correct")), None)
    distractors = [o for o in opts if not o.get("is_correct")]

    # too many options → keep the correct one + the first 3 distractors
    distractors = distractors[:3]
    # too few → pad with clearly-wrong placeholder distractors (flagged for review upstream)
    while len(distractors) < 3:
        distractors.append({"text": "None of the above", "is_correct": False}
                           if not any((d.get("text") or "").strip().lower() == "none of the above"
                                      for d in distractors)
                           else {"text": f"(distractor {len(distractors)})", "is_correct": False})

    if correct_opt is None:  # degenerate: no usable option at all
        correct_opt = {"text": "(correct answer unavailable)", "is_correct": True}

    mcq["options"] = [correct_opt] + distractors  # position fixed by the variety pass below


def check_and_fix(mcqs: list[dict], *, rng: random.Random | None = None) -> dict:
    """Validate a subtopic's MCQs. Repairs option count, reshuffles answer positions to
    near-uniform, and rebalances trivially. Returns {items, violations, regen}. Each mcq
    is fixed in place (exactly 4 options relabeled A-D, non-null answer_key set)."""
    rng = rng or random.Random(1234)
    violations: list[str] = []
    regen: list[int] = []

    # per-item structural validation + deterministic repair
    for i, mcq in enumerate(mcqs):
        issues = _item_ok(mcq)
        if issues:
            violations.append(f"item {i}: {'; '.join(issues)}")
            if any("options" in x or "correct" in x for x in issues):
                regen.append(i)
        _coerce_four(mcq)  # guarantees 4 options + one correct

    # answer-position variety: distribute correct answers near-uniformly across A-D
    target_positions = [_LABELS[i % 4] for i in range(len(mcqs))]
    rng.shuffle(target_positions)
    for i, mcq in enumerate(mcqs):
        opts = mcq.get("options", [])
        correct = next((o for o in opts if o.get("is_correct")), None)
        others = [o for o in opts if not o.get("is_correct")]
        if correct is None or len(others) != 3:
            # _coerce_four should prevent this; last-resort fallback keeps answer_key valid
            mcq["answer_key"] = (opts[0]["label"] if opts and opts[0].get("label") else "A")
            continue
        want = target_positions[i] if i < len(target_positions) else "A"
        ordered = []
        oi = 0
        for lbl in _LABELS:
            if lbl == want:
                ordered.append(correct)
            else:
                ordered.append(others[oi]); oi += 1
        for lbl, o in zip(_LABELS, ordered):
            o["label"] = lbl
        mcq["options"] = ordered
        mcq["answer_key"] = want

    # aggregate length balance
    correct_lens, incorrect_lens = [], []
    for mcq in mcqs:
        for o in mcq.get("options", []):
            (correct_lens if o.get("is_correct") else incorrect_lens).append(len(o.get("text", "")))
    if correct_lens and incorrect_lens:
        mc, mi = sum(correct_lens) / len(correct_lens), sum(incorrect_lens) / len(incorrect_lens)
        if mi and mc > mi * 1.4:
            violations.append(
                f"correct options systematically longer (mean {mc:.0f} vs {mi:.0f}) — "
                "consider regen for length balance")

    return {"items": mcqs, "violations": violations, "regen": sorted(set(regen))}
