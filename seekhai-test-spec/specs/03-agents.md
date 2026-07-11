# 03 — Agents

Every agent has a fixed contract: **inputs**, **outputs**, **model class**, **tools it may
call**, and **failure behaviour**. Models are resolved from `models.yaml`; the "model class"
column is a hint, not a hardcoded ID.

| # | Agent | Phase | Model class |
|---|-------|-------|-------------|
| 0 | Prompt Guardrail | all input points | fast (classifier) |
| 1 | Intent Classification | intake | fast |
| 2 | Clarification ("Ask User Question") | intake | fast |
| 3 | Domain Grounding | intake | fast |
| 4 | Course Architect | build | strong reasoning |
| 5 | Course Scout | build | strong + tools |
| 5b | Scouting Comprehensiveness Auditor | build | **Sonnet-class (independent)** |
| 6 | Cost Estimator | build | fast (mostly arithmetic + heuristics) |
| 6b | Cost Reconciliation | post-build | deterministic + fast LLM for "reason" |
| 7 | Content Generators (MCQ / Q&A / Content-panel / Hint / Diagram) | build | strong |
| 8 | Option Checker | build | fast/deterministic |
| 9 | Domain Checker | build | strong |
| 10 | Content Verification | build | **Gemini (independent)** |
| 11 | Q&A Grader | runtime | strong |
| 12 | Adaptive Controller | runtime | fast (mostly rules + light judgment) |
| 12b | Root-Cause Weakness (build) + Follow-up Generator (build+runtime) | build + runtime | fast (map) / strong (generate) |
| 13 | Personalization (per-learner, cross-course) | build + post-session | fast |

Agents 1–3 are specified in `01-personas-and-intent.md`; the Scouting Auditor (5b) is detailed
in `05-content-pipeline-and-tools.md §4`. This file details 0, 4–12.

---

## 0. Prompt Guardrail Agent

Runs at **every point a user types free text**: the course-creation prompt, clarification
answers, Q&A answers, and both feedback boxes. Guardrails are non-negotiable and always on.

**Checks (fast classifier + rules):**
- **Injection / jailbreak** — attempts to override system instructions, extract prompts, or
  redirect agents (critical on Q&A/feedback text that later flows into LLM context).
- **On-topic / on-task** — course-creation prompts must be a learnable topic; reject abuse,
  nonsense, or attempts to make the tool do unrelated work.
- **Safety** — disallowed/harmful content.
- **PII** — flag secrets/credentials a tester might paste; strip before persistence/logging.
- **Length / format** — enforce sane bounds.

**Behaviour:** on a violation, return a clear, friendly reason to the UI and block submission
(course prompt) or neutralise the input (feedback/Q&A: sanitise + annotate, don't execute
embedded instructions). All verdicts are logged (`guardrail_events`, see `06`).

**Output:** `{ allow: bool, category: str|null, sanitized_text: str, user_message: str|null }`

---

## 4. Course Architect Agent

Turns `CourseContext` into a calibrated curriculum.

**Responsibilities**
- Decompose the topic into **topics → subtopics**, ordered pedagogically (prerequisites first).
- For **each topic**, assign a **calibrated DL** (1/2/3) representing how hard that topic
  *inherently* is for this persona. Harder topics are examined at DL3; foundational ones at DL1.
- Set a target **question count per subtopic** (feeds the population UI).
- Respect persona: a `high`/`business` learner gets fewer DL1 foundations and more DL3;
  a `junior`/`general` learner gets a longer DL1 ramp.
- Record assumptions (from clarification cap) as curriculum notes.

**Input:** `CourseContext`
**Output:** `Curriculum`
```json
{
  "title": "...",
  "topics": [{
    "name": "...", "order": 1, "calibrated_dl": 2,
    "rationale": "why this DL for this persona",
    "subtopics": [{
      "name": "...", "description": "...", "order": 1,
      "target_question_count": 5,
      "first_interaction": "definition_mcq"
    }]
  }],
  "assumptions": ["..."]
}
```

**Failure:** if the topic is non-AI (out of scope) or incoherent, return a structured refusal
with a suggested reframing rather than fabricating a curriculum.

---

## 5. Course Scout Agent

Finds *where each subtopic's content should come from* on the live web.

**Tools:** `web_scrape`, `paper_downloader`, `illustration_scraper` (see `06`).
**Responsibilities**
- For each subtopic, search and rank sources: official docs, reputable AI blogs, and — when
  `currency_mode = latest_research` — recent arXiv/conference papers.
- Prefer primary sources over aggregators. Deduplicate. Capture publication date so
  "recent" actually means recent.
- Identify candidate **diagrams/figures** in those sources for later extraction.
- Produce a per-subtopic **source manifest**.

**Output:** `source_manifest`
```json
{
  "<subtopic_id>": [
    {"url": "...", "type": "paper|doc|article|illustration",
     "title": "...", "published": "2026-05-01", "figure_candidates": [ "..." ],
     "relevance": 0.0}
  ]
}
```

**Failure:** if a subtopic yields no acceptable sources, flag it (don't invent citations) so
the Architect can merge/drop it or the user can be warned in the population UI.

---

## 5b. Scouting Comprehensiveness Auditor Agent

An **independent Sonnet-class LLM** that judges whether each subtopic's Content Package is
genuinely comprehensive **before** generation is allowed to start. Full contract, checks, and
loop behaviour are in `05-content-pipeline-and-tools.md §4`. Summary: it scores coverage,
source diversity, depth-vs-DL, recency, and figure availability; on failure it returns
`recommended_actions` that send the Scout back for more (bounded by `MAX_SCOUT_ROUNDS`,
default 3). This gate exists because course quality is bounded by scouting quality.

---

## 6. Cost Estimator Agent

Estimates the **token cost of building the whole course** and gates the build.

**Method (deterministic + heuristic):**
- Per subtopic: `target_question_count` × (avg tokens per MCQ + Q&A + hints + content panel +
  diagram handling) × (generation + 3 checkers + verification passes) + scouting overhead.
- Multiply by per-model prices from `models.yaml`. Add a contingency buffer (default 15%).
- Output a breakdown by phase (scouting / generation / checking / verification) and by subtopic.

**Output:** `CostEstimate`
```json
{
  "currency": "USD",
  "total_estimate": 0.00,
  "buffer_pct": 15,
  "by_phase": {"scouting": 0.0, "generation": 0.0, "checking": 0.0, "verification": 0.0},
  "by_subtopic": [{"subtopic_id": "...", "estimate": 0.0}],
  "assumptions": ["avg tokens per item, retries assumed, ..."]
}
```

**Gate:** the build graph pauses (`cost_gate`) and does not generate any paid content until
the user approves. On rejection, the build ends; the user can revise scope and re-run.

---

## 6b. Cost Reconciliation Agent

Runs **after** the build completes. It sums the **actual** token cost incurred (from
`generation_metrics`), computes the **delta vs the estimate**, and explains the delta.

- **Actual cost** = sum of real per-call costs across scouting, generation, checking,
  verification (including all retries/regens and extra scout rounds).
- **Delta** = `actual − estimated` (absolute + %).
- **Reason** = a short, attributed explanation (deterministic attribution + a brief LLM
  summary): e.g. "3 extra scout rounds on 2 subtopics (+X), 11 verification regens (+Y),
  fewer questions than estimated on subtopic Z (−W)."

**Output:** `CostReconciliation`
```json
{
  "estimated": 0.00, "actual": 0.00,
  "delta_abs": 0.00, "delta_pct": 0.0,
  "drivers": [
    {"phase": "scouting", "estimated": 0.0, "actual": 0.0, "reason": "extra scout rounds"},
    {"phase": "verification", "estimated": 0.0, "actual": 0.0, "reason": "regens on failed items"}
  ],
  "summary": "one-paragraph explanation of the delta"
}
```
Persisted to `courses` (see `06 §5`) and shown on the curriculum/population page.

---

## 7. Content Generators

A family of sub-agents run per subtopic. All must ground examples in `domain_grounding`.

### 7a. Content-panel Generator
Produces the per-interaction **content panel**: what the concept is, how it works, key
definitions — written for the persona. This is what the **Content** button reveals. It is
**personalized per interaction**, not a generic topic dump.

### 7b. MCQ Generator
- The **first interaction of every subtopic is a definition MCQ** ("What is the definition of
  X?").
- Exactly **4 options**; one correct.
- The **question** may include a diagram; **options must not** contain diagrams (text only).
- Emits `answer_key`, per-option text, and metadata for the Option Checker.

### 7c. Q&A Generator
- Free-response items on the same subtopic, gradable by rubric.
- Question may include a diagram. Emits a **grading rubric** (key points, weighting) for the
  Q&A Grader.

### 7d. Hint Generator
Produces a **3-rung hint ladder per interaction**, personalized to that exact question:
1. **Hint 1** — general nudge; must **not** reveal the answer.
2. **Hint 2** — more specific; narrows it down.
3. **Hint 3** — reveals the correct answer (with brief why).

### 7e. Diagram Agent
- Attaches diagrams to questions where they aid understanding (MCQ + Q&A).
- Sources figures from scouted papers/pages via `vision_image_extractor`, or the
  `illustration_scraper`. If no suitable figure exists and one is clearly needed, generate a
  simple schematic (SVG) — record provenance (`sourced` vs `generated`).
- Diagrams are stored as blobs in local Postgres (`blobs` bytea, via the `BlobStore` interface);
  interactions reference them by `diagram_ref` (a `blobs.id`).

### 7g. Interaction Generator (agent-chosen format)
For each non-definition slot, this generator **chooses the interaction format that best teaches
the concept** and produces it: `mcq` (default), `order` (processes/pipelines), `blanks`
(terminology/params/code fragments, from a word bank), or `dragdrop` (architecture component
roles). It always emits a `content_panel_md` + 3-rung hints. Non-mcq bodies are **validated for
internal consistency** (ids resolve, every box/blank has a correct answer, ranges/counts sane)
so runtime grading is deterministic; invalid bodies fall back to `mcq`. All formats are scored
and escalate like an MCQ (`04 §1/§4`). Model class: **strong**.

### 7f. Code-Walkthrough Generator (technical learners)
Produces a **guided read-only code walkthrough** for `orientation = technical`: a small,
idiomatic code example (1-3 short files) plus **concept steps that each highlight the relevant
line ranges** (may switch files), and a **paired MCQ** that tests understanding of the code.
Line ranges are validated/clamped to each file's real length. Stored as a `walkthrough`
interaction (`04 §1`, `06 §1`). Model class: **strong**. Best-effort — a failure never breaks
the build.

**Generator output:** a list of `Interaction` objects (see `06-data-and-feedback.md` schema),
each with question, options/rubric, hint ladder, content panel, optional diagram, DL, and
`gen_latency_ms`.

---

## 8. Option Checker Agent

Validates MCQ **structure** across the whole subtopic/course. Mostly deterministic.

**Must enforce:**
- **Exactly 4 options** per MCQ.
- **Answer-position variety** — the correct answer must not sit at the same label (A/B/C/D)
  repeatedly. Enforce a near-uniform distribution across each subtopic; shuffle to fix.
- **Length balance** — correct and incorrect options must have comparable length *in
  aggregate*. It must not be the case that the correct option is systematically longer
  (a common give-away). Check mean/though also flag per-item outliers.
- Options are mutually exclusive, plausible distractors, text-only (no diagrams).

**Output:** pass, or a list of violations with an auto-fix (reshuffle/rebalance) or a regen
request when content-level rewrite is needed.

---

## 9. Domain Checker Agent

Validates that generated content is **framed in the domain grounding**.

- Example: role "VP of AmEx" ⇒ content should use American Express / credit-card / payments
  examples. If the generator produced generic examples, the checker flags it and requests
  regeneration with the domain made explicit.
- For neutral grounding (`must_ground = false`), it only checks topical relevance.

**Output:** per-item verdict `{on_domain: bool, reason, regen_hint}`.

---

## 10. Content Verification Agent (Gemini)

An **independent model** (latest Gemini) checks all generated content for **factual
accuracy**. Using a different model family from the generator is deliberate — it reduces
correlated errors.

**Checks per item:**
- Is the stated correct answer actually correct?
- Are definitions/explanations in the content panel accurate and current?
- Do distractors avoid being accidentally-correct?
- Are diagram claims consistent with the question?

**Output:** `{verdict: pass|fail, issues: [...], suggested_fix}`. On `fail`, request regen
(within retry budget); after budget, mark for human review and surface in the population UI.

---

## 11. Q&A Grader Agent (runtime)

Grades a learner's free-text answer against the item's rubric.

**Input:** learner answer + rubric + DL + hints used.
**Output:**
```json
{
  "correct": true,
  "rubric_hits": ["key point 1", "..."],
  "rubric_misses": ["..."],
  "raw_band": "full | partial | incorrect",
  "feedback_md": "concise, persona-appropriate feedback",
  "suggested_score": 4
}
```
Scoring uses the same rubric as MCQ (see `04`): base `DL × 2`, minus `1` per hint used. The
grader proposes the band; the scoring service computes the final number so scoring stays in
one place.

**Student-facing feedback (required):** `feedback_md` is **shown to the learner** after they
submit a Q&A answer — it must explain what they got right (`rubric_hits`), what they missed
(`rubric_misses`), and the correct reasoning, written for their persona. This is the learner's
takeaway on their own written answer, not just an internal grading artefact. It is persisted
(`responses.grade_feedback_md`) and rendered per `07-frontend-ui.md §2`.

---

## 12. Adaptive Controller (runtime)

Chooses what happens next. Mostly rules with light judgment.

**Decides:**
- Next subtopic / interaction order.
- **Current DL** for the learner: start at the topic's calibrated DL, then adapt — sustained
  success nudges DL up (toward DL3), repeated errors nudge DL down and inject review.
- Whether to **inject a review interaction** on a flagged weakness.
- When a subtopic / course is complete.

**Also owns the escalation rule:** on a wrong MCQ it triggers the immediate same-subtopic Q&A
and passes control accordingly.

**Weakness flagging:** increments `weakness_counts[subtopic]` when a learner scores below
`WEAKNESS_THRESHOLD` (default: wrong MCQ, or Q&A `incorrect`/`partial`). Persists to
`weaknesses` (see `06`).

---

## 12b. Root-Cause Weakness Agent (build-time reserve) + Follow-up Generator (runtime)

Two closely-related jobs power the MCQ→Q&A root-cause loop (`04 §4`), split so the runtime
never scrapes:

**Root-Cause Weakness agent (build).** Per subtopic, reads the Content Package and maps the
**common misconceptions / prerequisite gaps** a learner is likely to hold, and proposes
**targeted queries** for extra remediation material. Its output plus a small bounded extra
scout become the subtopic's **reserve** (`05 §10`). Model class: **fast** (light judgment).

```json
{ "misconceptions": [{"root_cause": "...", "probe_focus": "...", "remediation": "..."}],
  "prerequisite_gaps": ["..."], "search_queries": ["..."] }
```

**Follow-up Generator (build + runtime).** Turns one misconception + the reserve into a
**simple, plain-language follow-up Q&A** — easier than the MCQ (`DL−1`), a short prose answer,
**no equation-writing**. The **seed** follow-up is pre-generated at build time
(`role = followup_seed`); **probes** are generated at runtime from the reserve only
(`role = followup_probe`), one fast LLM call each, **no web/MCP calls**. Model class:
**strong** (same generator family as `§7c`), but bounded to a single call per probe.

---

## 13. Personalization Agent (per-learner, cross-course)

A learner's identity (name-only signup, `01 §5`) is the key to **everything they've done**.
This agent distills that history into a reusable **profile** so each new course is tuned to
this specific learner — not a generic persona.

**Inputs (deterministic signals):** across *all* the learner's sessions — attempts, accuracy,
average hints used, their most-missed subtopics (weaknesses), and their past course titles.

**Output (profile):**
```json
{
  "summary_md": "2-4 sentences: their level, consistent strengths, recurring struggles",
  "directives": {
    "emphasize_subtopics": ["reinforce with extra scaffolding / review"],
    "can_accelerate": ["mastered — go harder / skip basics"],
    "preferred_difficulty_bias": "easier|balanced|harder",
    "framing_notes": "recurring framing that helps this learner"
  },
  "signals": { "attempts": 0, "accuracy_pct": 0, "avg_hints": 0.0, "weak_areas": [], "past_courses": [] }
}
```

**When it runs:** (a) **before a build** — `context_for_build(user_id)` injects the profile
into `CourseContext.personalization`, which the **Course Architect** (`§4`) and generators use
to bias difficulty, add scaffolding on known weak areas, and skip mastered basics; (b) **after
a session completes** — the profile is refreshed from the updated history. Persisted in
`user_profiles` (`06 §1`). Model class: **fast**. **Degrades gracefully**: a brand-new learner
yields an empty profile (no change to default behaviour); any LLM failure falls back to the
deterministic signals alone.

---

## Shared conventions

- **All agent outputs are strict JSON** matching the contracts above; parse defensively and
  reject malformed output with one retry before failing the node.
- **Every agent call logs** model, tokens in/out, latency, cost, and a trace id.
- **Prompts live in `prompts/<agent>.md`**, versioned, so they can be iterated without code
  changes and diffed in observability.
