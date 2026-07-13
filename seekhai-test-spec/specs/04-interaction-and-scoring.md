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

### Richer scored interactions (agent-chosen)
Beyond the MCQ, three more formats test a concept — and the **interaction generator chooses
the best format per concept** (`03 §7g`), so a process becomes an ordering task, an
architecture becomes a drag-drop, terminology becomes fill-in-the-blanks:
- **`order`** — arrange steps into the correct sequence (processes/pipelines).
- **`blanks`** — fill blanks in a sentence/code snippet from a word bank (terminology, params).
- **`dragdrop`** — drag entities into the labelled boxes of an architecture diagram (structure,
  component roles).

**These are equivalent to an MCQ**: scored **all-or-nothing** with the *same* formula
(`DL × 2` − hints), and a **wrong answer triggers the identical Q&A root-cause escalation**
(§4). Grading is **deterministic** (pure Python from a validated `payload`) — no runtime LLM —
and the correct answer is **stripped** before the interaction is served, then revealed after
submit. The first interaction of a subtopic is still the **definition MCQ**. Stored in
`interactions.payload` (`06 §1`); rendered per `07 §2`.

### Q&A
- Free-text response, graded by the Q&A Grader against a rubric.
- Question may include a diagram.
- **Q&A is a follow-up, not a main-sequence item.** A learner reaches Q&A **only** as the
  **escalation** after a wrong MCQ (§4). The main learning sequence is MCQ-only; standalone
  Q&A are not interleaved into it.
- **Follow-ups must be simple.** The learner is already struggling, so a follow-up is
  **easier** than the MCQ it follows (generated at `DL−1`), asks for a **short prose answer**
  (one or two sentences), and **never asks the learner to write equations or notation** —
  they can't type math comfortably on this screen (content-feedback finding, `06 §7`). Math
  in the *question* is rendered (LaTeX, `07 §1`); the *answer* stays plain-language.

### Guided code walkthrough (technical learners)

A **read-only, stepped code tour** for `orientation = technical` learners: a small realistic
code example (file tree + syntax-highlighted viewer) where each **concept step highlights the
relevant line range(s)** and can switch files. It is **not scored** — the learner reads it and
marks it reviewed — and it is **immediately followed by a paired MCQ** that tests the code
(which escalates to Q&A on a wrong answer like any other MCQ). Generated at build time
(`03 §7f`) and appended to the subtopic; stored on the interaction (`type = walkthrough`,
`interactions.walkthrough` JSON, `06 §1`). Line ranges are validated/clamped so the UI can
never receive an out-of-bounds highlight. Rendered per `07 §2`.

**Diagram rule (both types):** diagrams appear **in questions, never in answer choices.**

**Difficulty visibility (required):** every question shows its **difficulty level** (DL1
Easy / DL2 Medium / DL3 Hard) to the learner, on both MCQ and Q&A (`07 §2`).

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

**Display order (required):** hints are revealed one rung at a time, but **all revealed rungs
stay on screen**. The **most recently revealed** rung shows **first (on top)**, with earlier
rungs kept **below** it — so tapping for Hint 2 shows Hint 2 above Hint 1, Hint 3 above both,
etc. The learner never loses access to an earlier hint after escalating (`07 §2`).

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

## 4. MCQ → Q&A escalation (root-cause follow-up loop)

A wrong MCQ triggers a **diagnostic follow-up loop** whose goal is to find the **root cause**
of the misunderstanding, not just score a second question. It is designed so the learner can
recover the concept in **plain language**, and so the runtime **never scrapes the web**
mid-session (see the build-time reserve, `05 §10`).

```mermaid
sequenceDiagram
  participant L as Learner
  participant E as Engine
  participant G as Q&A Grader
  L->>E: submit MCQ answer
  alt correct
    E->>E: item_score = DL*2 - hints; advance to next MCQ
  else wrong
    E->>E: MCQ item_score = 0
    E->>L: serve PRE-GENERATED seed follow-up Q&A (same subtopic, DL-1, plain-language)
    L->>E: submit short free-text answer
    E->>G: grade against rubric
    alt full
      E->>E: score it; clear follow-up; advance to next MCQ
    else partial / incorrect
      E->>E: flag weakness; generate NEXT root-cause probe from the RESERVE (no scraping)
      E->>L: serve probe (targets the specific misconception)
      note over E,L: loop up to MAX_PROBE_ROUNDS, then return to the main sequence
    end
  end
```

Rules:
- The **first** follow-up is **pre-generated at build time** (the *seed follow-up*, `05 §10`)
  so it appears instantly.
- Each subsequent **root-cause probe** is generated **at runtime from the subtopic's
  reserve** — a single fast LLM call, **no web search / MCP / scraping** (that would be far
  too slow inside a session). Probes rotate through the misconceptions the Root-Cause
  Weakness agent mapped at build time.
- The loop is bounded by **`MAX_PROBE_ROUNDS`** (default 3, in config). A **full** answer at
  any point clears the follow-up and returns to the next **main MCQ**; exhausting the rounds
  also returns to the main sequence (with the weakness recorded).
- Every follow-up is on the **same subtopic** as the missed MCQ, is **simpler** than it, and
  reuses the same hint/content affordances. Follow-ups are stored as interactions with
  `role in {followup_seed, followup_probe}` and never appear in the main MCQ sequence
  (`06 §1`).

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
followup:                     # MCQ→Q&A root-cause loop (§4)
  max_probe_rounds: 3         # runtime probes after the pre-generated seed follow-up
  reserve_extra_sources: 2    # extra sources scouted at build time for the reserve (05 §10)
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
chat:                         # in-course study assistant (§9)
  query_char_limit: 300
  answer_char_limit: 2000     # generous backstop only — the assistant answers for quality
  top_k: 5
```

---

## 9. In-course study assistant

A purely-text chatbot, available on the learning screen **once the learner has started the
questions** (i.e. a session exists). It answers the learner's free-text questions — checking the
current course's material first, then giving the best answer it can.

**Check the course material first (RAG).** For every question the assistant retrieves from the
**current course's own knowledge base** (`06 §6`, persisted content, no regeneration): subtopic
names/descriptions, per-interaction **content panels**, question text + pre-generated **model
answers**, and the **correct MCQ option** text. Retrieval is a lightweight **in-process BM25**
(top-k, `k≈5`) — it spends **no tokens**.

**Recall of rare terms (required).** BM25's top-k is followed by a **term-coverage pass**: for
each *discriminating* query term that exists **anywhere** in the course, at least one chunk
containing it is pulled into the retrieved set (up to a small cap), even if chunks matching
several *other* query words outscored it — otherwise a term living in a *different* subtopic than
the rest of the question loses the ranking and the assistant would wrongly conclude the course
doesn't cover it.

**Answer for quality, course-first (product decision).** The retrieved passages plus the question
go to **GLM 5.2** (`course_chat` in `models.yaml`). The assistant is told to **prefer and stay
consistent with the course material**, but it may **go beyond the course using its own knowledge
whenever that yields a better, more complete or more correct answer** — e.g. explaining a concept
the course only mentions, comparing the course's ideas to a tool/framework the course doesn't
cover, or correcting a misconception. When it draws on knowledge **not** in the course material it
**signals that** ("Beyond what this course covers, …") so the learner can tell course content from
wider context; it must never claim the course covers something absent from the CONTEXT, nor claim
it omits something present. Accuracy comes first. (This deliberately replaces the earlier
strictly-grounded/refuse behaviour — answer quality was chosen over token cost.) The `chat`-phase
cost is recorded to `generation_metrics` and folds into the **Q&A-feedback** bucket (`06 §9`).

**Limits.** The learner's **question is capped at 300 characters** (UI *and* server-side). The
answer length is **no longer tightly capped** — a generous 2000-char server backstop only — since
the goal is the best answer, not the cheapest.

**Persistent, per-learner history (required).** The assistant is **one assistant per learner**,
not per course: every exchange (question + answer, with the course it was asked in, a timestamp,
and the course subtopics consulted) is stored in `assistant_messages` (`06 §10`). The panel
**restores the full conversation on open/refresh** and shows the learner's questions **across all
their courses**, each labelled with its course name and date/time.

**Endpoints & safety.** `POST /api/sessions/{session_id}/chat { query }` — the session authorises
the call, pins the course, and identifies the learner (for history). The query passes the **prompt
guardrail** (`03 §0`) at the `chat` entry point (neutralised, not blocked). Response:
`{ answer, grounded, sources, id, created_at, course_name }`. `GET /api/users/{user_id}/chat`
returns the learner's whole history. The UI (`07 §2`) is a small docked chat panel with a 300-char
counter; each answer carries a 👍/👎 (`06 §8`).
