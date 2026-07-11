"""Option Checker (spec 03 §8). Mostly deterministic MCQ structure validation across a
subtopic: exactly 4 options, answer-position variety (reshuffle to near-uniform), and
aggregate length balance (flag if the correct option is systematically longer).
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


def check_and_fix(mcqs: list[dict], *, rng: random.Random | None = None) -> dict:
    """Validate a subtopic's MCQs. Reshuffles answer positions to near-uniform and
    rebalances trivially. Returns {items: [...fixed], violations: [...], regen: [idx...]}.
    Each mcq is fixed in place (options relabeled A-D, answer_key set)."""
    rng = rng or random.Random(1234)
    violations: list[str] = []
    regen: list[int] = []

    # per-item structural validation
    for i, mcq in enumerate(mcqs):
        issues = _item_ok(mcq)
        if issues:
            violations.append(f"item {i}: {'; '.join(issues)}")
            if any("options" in x for x in issues):
                regen.append(i)

    # answer-position variety: distribute correct answers near-uniformly across A-D
    target_positions = [_LABELS[i % 4] for i in range(len(mcqs))]
    rng.shuffle(target_positions)
    for i, mcq in enumerate(mcqs):
        opts = mcq.get("options", [])
        if len(opts) != 4:
            continue
        correct = next((o for o in opts if o.get("is_correct")), None)
        others = [o for o in opts if not o.get("is_correct")]
        if correct is None or len(others) != 3:
            continue
        want = target_positions[i]
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
