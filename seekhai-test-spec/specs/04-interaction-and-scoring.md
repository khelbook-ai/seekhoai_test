# 04 — Interaction Engine & Scoring

This is the heart of the runtime. Everything the learner does is an **interaction**; content
and hints exist only to help complete interactions.

---

## 1. Interaction types

### MCQ
- Exactly **4 options**, one correct (enforced by Option Checker).
- The **question** may include a diagram; **options are text-only**.
- The first interaction of every subtopic is the **definition MCQ**: "What is the definition
  of `<subtopic>`?" — e.g. for a learner starting MCP, the very first thing shown is an MCQ
  asking for the definition of MCP.

### Q&A
- Free-text response, graded by the Q&A Grader against a rubric.
- Question may include a diagram.
- Used both as standalone items and as the **escalation** after a wrong MCQ.

**Diagram rule (both types):** diagrams appear **in questions, never in answer choices.**

---

## 2. Per-interaction affordances

Every interaction — with no exceptions — carries:

| Affordance | Behaviour |
|-----------|-----------|
| **Content button** | Reveals the interaction's personalized content panel: what the concept is, how it works, definitions. Personalized per interaction and persona. |
| **Hint button** | Serves the next rung of the 3-hint ladder. Each rung is personalized to this exact question. |

Placement of these two buttons is a **primary UX requirement** — see `07-frontend-ui.md`.

### Hint ladder
| Rung | Content | Score effect |
|------|---------|--------------|
| Hint 1 | General nudge, does **not** reveal the answer | −1 |
| Hint 2 | More specific, narrows it down | −1 |
| Hint 3 | Reveals the correct answer + brief why | −1 |

Hints are pre-generated at build time and simply served at runtime.

---

## 3. Scoring

**Base score per interaction** = `DL × 2`:

| DL | Base |
|----|------|
| DL1 | 2 |
| DL2 | 4 |
| DL3 | 6 |

**Hint penalty:** `−1` per hint used on that interaction (max −3).

**Formula:**
```
item_score = max(SCORE_FLOOR, (DL × 2) − hints_used)   # if answered correctly
item_score = 0                                          # if answered incorrectly (MCQ)
```
- `SCORE_FLOOR` default = **0** (configurable). This matters because at DL1 with 3 hints the
  raw value is `2 − 3 = −1`; the floor clamps it. → *Confirm in open decisions.*
- A **wrong MCQ scores 0**, then triggers an escalated Q&A that is scored on its own using
  the same formula — a second chance to earn points on the concept. → *Confirm in open decisions.*
- **Q&A partial credit:** the Grader's band maps to a fraction of base before hint penalty:
  `full → 1.0`, `partial → 0.5`, `incorrect → 0`. Then subtract hints, then clamp to floor.
  → *Confirm partial-credit policy in open decisions.*

`running_score` is the session sum. Persist both per-item and running totals.

---

## 4. MCQ → Q&A escalation

```mermaid
sequenceDiagram
  participant L as Learner
  participant E as Engine
  participant G as Q&A Grader
  L->>E: submit MCQ answer
  alt correct
    E->>E: item_score = DL*2 - hints; advance
  else wrong
    E->>E: MCQ item_score = 0
    E->>L: serve Q&A on SAME subtopic (diagram if useful)
    L->>E: submit free-text answer
    E->>G: grade against rubric
    G-->>E: band + feedback
    E->>E: qa_item_score per formula
    E->>E: flag weakness on this subtopic
  end
```

The escalated Q&A is on the **same subtopic** as the missed MCQ and reuses the same hint/
content affordances.

---

## 5. Adaptivity (3 levels)

- Each **topic** has a **calibrated DL** from the Architect (how hard it inherently is).
  Harder topics are examined at DL3; foundational at DL1.
- Within a session the **learner's working DL** adapts:
  - Start each topic at its calibrated DL.
  - **Promote** (toward DL3) after sustained success (default: `PROMOTE_STREAK = 2` correct at
    the current DL with `< 1` hint each).
  - **Demote** (toward DL1) and inject review after repeated errors
    (default: `DEMOTE_ERRORS = 2` within a subtopic).
- Adaptivity is owned by the Adaptive Controller (`03-agents.md#12`). Thresholds live in
  config, not code.

---

## 6. Weakness tracking

- A **weakness** is recorded when a learner scores below `WEAKNESS_THRESHOLD` on a subtopic
  (default: wrong MCQ, or Q&A `incorrect`/`partial`).
- `weakness_counts[subtopic]` increments; the record stores subtopic ref, count, last-seen.
- The Adaptive Controller may **inject review interactions** on high-count weaknesses.
- Weaknesses surface to the learner on the **dashboard**: *which topics they made mistakes in*
  and *which topics they need to improve* (`07-frontend-ui.md`). This is a required feature.

---

## 7. Content feedback per interaction

Every interaction has a **content feedback section** where a human comments on the *quality of
that interaction's content*. This feedback is:
- Stored in Postgres (`content_feedback`), **and**
- Persisted as a `.md` file under a folder structure keyed by **course name / subtopic name**
  (exact path scheme in `06-data-and-feedback.md`).

Content feedback is distinct from **application feedback** (comments on how a *page* works),
which appears on the course-creation and final-feedback pages (see `06` and `07`).

---

## 8. Configuration surface (defaults)

```yaml
scoring:
  base_multiplier: 2
  hint_penalty: 1
  score_floor: 0
  qa_partial_credit: { full: 1.0, partial: 0.5, incorrect: 0.0 }
adaptivity:
  promote_streak: 2
  demote_errors: 2
weakness:
  threshold: "wrong_mcq_or_qa_below_full"
clarification:
  max_questions: 10
  clarify_threshold: 0.7
  ambiguity_floor: 0.2
checkers:
  max_regen_retries: 2
cost:
  buffer_pct: 15
```
