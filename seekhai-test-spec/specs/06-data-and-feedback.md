# 06 — Data Model, Feedback & Observability

The backend must **capture everything**: the raw prompt, the generated curriculum, whether the
user accepted it, all feedback, every learner response, the DL of each question, all generated
content, **and the speed at which content is generated**.

> **Storage model (local-first).** Everything lives in a **local PostgreSQL** instance.
> Binary artefacts (diagrams, extracted figures, uploaded feedback images) are stored as
> **blobs in Postgres** (`bytea`) via a thin `BlobStore` interface, so a local-dir or S3
> backend can be swapped in later without changing callers. The **one thing on the local
> filesystem** is the required content-feedback `.md` tree and its linked image assets, written
> under a configurable directory (default `./data/feedback/…`). No cloud/AWS dependency.

```sql
-- Blobs (local): single home for all binary artefacts -------------------------
blobs(
  id uuid pk, kind text,                                   -- diagram|figure|feedback_image|source_pdf|...
  mime text, bytes bytea, byte_len int,
  sha256 text, created_at timestamptz
)
```


---

## 1. PostgreSQL schema (core tables)

```sql
-- Users & persona ------------------------------------------------------------
users(
  id uuid pk, name text, role_raw text, created_at timestamptz   -- name-only signup (01 §5)
)

-- Per-user, cross-course learning profile maintained by the Personalization agent (03 §13).
user_profiles(
  id uuid pk, user_id uuid fk unique,
  summary_md text,                                       -- "who this learner is"
  directives jsonb, signals jsonb,                       -- tuning hints + derived stats
  updated_at timestamptz
)

intent_profiles(
  id uuid pk, user_id uuid fk, orientation text,        -- technical|business|general
  seniority text,                                        -- junior|mid|high
  confidence numeric, domain_grounding jsonb, created_at timestamptz
)

-- Course creation ------------------------------------------------------------
courses(
  id uuid pk, user_id uuid fk, title text,
  raw_prompt text,                                       -- prompt entered by the user
  currency_mode text,                                    -- fundamentals|latest_research
  curriculum jsonb,                                       -- the populated curriculum
  accepted bool,                                          -- did the user accept it?
  cost_estimate jsonb, cost_approved bool,
  cost_actual numeric,                                   -- real cost incurred (reconciliation)
  cost_delta_abs numeric, cost_delta_pct numeric,        -- actual - estimate
  cost_reconciliation jsonb,                             -- drivers + reason for delta
  cost_md_path text,                                     -- path to the cost-delta .md (§5)
  status text, created_at timestamptz
)

clarification_qas(
  id uuid pk, course_id uuid fk, ordinal int,
  question text, options jsonb, answer text,
  multi_select bool default false                          -- question accepts several answers (01 §3)
)

topics(
  id uuid pk, course_id uuid fk, name text, ordinal int,
  calibrated_dl int, rationale text
)

subtopics(
  id uuid pk, topic_id uuid fk, name text, description text,
  ordinal int, target_question_count int, source_manifest jsonb,
  reserve jsonb                                            -- weakness-remediation reserve (05 §10)
)

sources(
  id uuid pk, subtopic_id uuid fk, url text, type text,   -- paper|doc|article|illustration
  title text, published date, license_hint text, scraped_at timestamptz, meta jsonb
)

-- Generated content ----------------------------------------------------------
interactions(
  id uuid pk, subtopic_id uuid fk, type text,             -- mcq|qa
  role text default 'main',                               -- main | followup_seed | followup_probe (04 §4)
  dl int, ordinal int,
  question_md text, diagram_ref uuid,                     -- fk to blobs.id, nullable
  content_panel_md text,                                  -- personalized content
  qa_rubric jsonb,                                         -- for qa items
  answer_key text,                                         -- for mcq items — NEVER null (see §7)
  gen_model text, gen_latency_ms int,                     -- generation SPEED capture
  gen_tokens_in int, gen_tokens_out int,
  reused_from uuid,                                        -- library origin if cloned (05 §11)
  created_at timestamptz
)

-- Content-reuse library: registry of built subtopics so similar future courses can reuse
-- their generated content instead of regenerating (05 §11).
content_library(
  id uuid pk, subtopic_name text, subtopic_norm text, topic_norm text,
  domain text, currency_mode text,
  source_subtopic_id uuid fk, source_course_id uuid fk,
  dl int, mcq_count int, qa_count int, illustration_count int,
  keywords jsonb, created_at timestamptz
)
-- `role` keeps follow-up Q&A out of the main MCQ sequence; the runtime serves them only
-- through the escalation path (04 §4). Only `role='main'` rows form the course flow.

mcq_options(
  id uuid pk, interaction_id uuid fk, label char,          -- A|B|C|D
  text text, is_correct bool, char_len int
)

hints(
  id uuid pk, interaction_id uuid fk, level int,           -- 1|2|3
  text_md text
)

diagrams(
  id uuid pk, interaction_id uuid fk, blob_id uuid fk,     -- fk to blobs.id
  provenance text,                                          -- sourced|generated
  source_url text, license_hint text,
  kind text, caption text, keywords jsonb, subtopic_name text  -- search metadata (05 §6)
)

-- Checks & verification ------------------------------------------------------
check_runs(
  id uuid pk, interaction_id uuid fk, checker text,        -- option|domain|verification
  verdict text, issues jsonb, model text, created_at timestamptz
)

-- Learning sessions ----------------------------------------------------------
sessions(
  id uuid pk, user_id uuid fk, course_id uuid fk,
  started_at timestamptz, ended_at timestamptz
)

responses(
  id uuid pk, session_id uuid fk, interaction_id uuid fk,
  user_answer text, is_correct bool, band text,            -- full|partial|incorrect (qa)
  dl int,                                                   -- DL of the question (captured)
  hints_used int, score_awarded int,
  graded_by text, grade_feedback_md text,
  escalated_from uuid,                                      -- the MCQ this QA followed, nullable
  probe_round int default 0,                                -- 0 = seed follow-up, 1..N = root-cause probes (04 §4)
  responded_at timestamptz
)

weaknesses(
  id uuid pk, user_id uuid fk, subtopic_id uuid fk,
  error_count int, last_seen timestamptz
)

-- Feedback -------------------------------------------------------------------
content_feedback(
  id uuid pk, interaction_id uuid fk, user_id uuid fk,
  feedback_md text, md_file_path text,                     -- mirror on local disk (.md tree)
  created_at timestamptz
)

application_feedback(
  id uuid pk, page_key text,                               -- course_creation|final_feedback|...
  user_id uuid fk, feedback_md text, created_at timestamptz
)

-- Image attachments for EITHER feedback type. A feedback entry may carry
-- multiple images, each optionally tied to a span of the text (caption/anchor).
feedback_images(
  id uuid pk,
  feedback_kind text,                                      -- content|application
  feedback_id uuid,                                        -- fk to content_feedback|application_feedback
  blob_id uuid fk,                                         -- fk to blobs.id (image bytes in Postgres)
  asset_path text,                                         -- local path when mirrored next to a .md file
  caption text,                                            -- the text this image is linked to
  ordinal int, created_at timestamptz
)

-- Guardrails -----------------------------------------------------------------
guardrail_events(
  id uuid pk, user_id uuid fk, entry_point text,           -- course_prompt|clarify|qa_answer|content_feedback|app_feedback
  raw_len int, allow bool, category text,                  -- injection|off_topic|safety|pii|length|null
  action text,                                             -- blocked|sanitized|allowed
  created_at timestamptz
)

-- Build-event log (tester-facing live build trace, spec 05 §9, 07 §5) ---------
build_events(
  id bigserial pk, course_id uuid fk,
  phase text,                                             -- intake|scouting|generation|checking|verification|persist|cost
  kind text,                                              -- web_search|scrape|extract|mcp|audit|generate|check|verify|warn|...
  message text, meta jsonb, created_at timestamptz
)

-- Metrics --------------------------------------------------------------------
generation_metrics(
  id uuid pk, course_id uuid fk, interaction_id uuid,      -- nullable for phase-level rows
  phase text,                                               -- scouting|generation|checking|verification
  model text, tokens_in int, tokens_out int,
  latency_ms int, cost numeric, created_at timestamptz
)
```

**Capture checklist (spec requirement → table):**
| Requirement | Where |
|-------------|-------|
| Prompt entered during course creation | `courses.raw_prompt` |
| Course curriculum populated | `courses.curriculum` + `topics`/`subtopics` |
| Whether user accepted curriculum | `courses.accepted` |
| Cost estimate + approval | `courses.cost_estimate`, `courses.cost_approved` |
| Content feedback | `content_feedback` (+ `.md` files) |
| Application feedback | `application_feedback` |
| Each learner response | `responses` |
| DL of each question | `interactions.dl`, `responses.dl` |
| All generated content | `interactions`, `mcq_options`, `hints`, `diagrams` |
| **Generation speed** | `interactions.gen_latency_ms`, `generation_metrics.latency_ms` |
| Q&A grader feedback shown to learner | `responses.grade_feedback_md` |
| Feedback image uploads (linked to text) | `feedback_images` (+ `.md` embeds) |
| Estimated cost | `courses.cost_estimate` |
| **Actual cost + delta + reason** | `courses.cost_actual`, `cost_delta_abs/pct`, `cost_reconciliation` |
| Guardrail decisions | `guardrail_events` |
| Follow-up role / probe round | `interactions.role`, `responses.probe_round` |
| Weakness-remediation reserve | `subtopics.reserve` |
| Multi-select clarification answers | `clarification_qas.multi_select` + joined `answer` |
| Learner identity + profile | `users.name`, `user_profiles` |
| Reused content provenance | `interactions.reused_from`, `content_library` |
| Illustration search metadata | `diagrams.kind/caption/keywords/subtopic_name` |
| Cost-delta reason file | `courses.cost_md_path` (+ `./data/cost/*.md`) |

---

## 2. Content-feedback `.md` file structure

Content feedback is mirrored to files, organised by **course name / subtopic name**:

```
feedback/
  <course_name_slug>/
    <subtopic_name_slug>/
      <interaction_id>.md
      <interaction_id>--02.md      # if multiple feedback entries on the same item
```

Each `.md` file carries front-matter, the text, **and any uploaded images embedded inline,
linked to the text they refer to**. Uploaded images are written next to the `.md`
(`<interaction_id>.assets/`) and referenced with relative paths, with the linked text used as
the caption/alt.

```markdown
---
course: "Understanding MCP"
subtopic: "MCP fundamentals"
interaction_id: "a1b2c3"
interaction_type: "mcq"
dl: 2
user_id: "..."
created_at: "2026-07-10T12:00:00Z"
images:
  - file: "a1b2c3.assets/shot-01.png"
    linked_text: "the diagram overlaps the option text here"
---

The distractor for option C is misleading because ...

> re: the diagram overlaps the option text here
![the diagram overlaps the option text here](a1b2c3.assets/shot-01.png)

... rest of the free-text feedback.
```

- Slugs are sanitised (lowercase, spaces→`-`, strip unsafe chars); readable course/subtopic
  names are preserved in front-matter.
- **Image ↔ text linking:** in the UI the tester can attach an image to a specific piece of
  their written feedback; that association is stored in `feedback_images.caption` and rendered
  in the `.md` as an embedded image directly beneath the quoted linked text (as above).
- Image bytes live in Postgres (`blobs`); when the `.md` is written, the image is also copied
  to a local `*.assets/` folder next to it (`feedback_images.asset_path`) so the `.md` renders
  standalone on disk.
- The whole `.md` tree (incl. `*.assets/`) is written under a configurable local directory
  (default `./data/feedback/…`); `content_feedback.md_file_path` keeps the DB row, blob, and
  file linked.

**Application feedback** supports the same image-upload + linking mechanism (via
`feedback_images` with `feedback_kind = application`), rendered inline in its own record.

**Application feedback** is *not* filed per-interaction; it's page-scoped and lives in
`application_feedback` (course-creation page, final student-feedback page, and any other page
that mounts the application-feedback widget).

---

## 3. Observability — decision

**Use LangSmith as the primary tracer, behind a thin abstraction that also supports Phoenix
(Arize).**

Reasoning:
- LangSmith has **native LangGraph integration** — every node, tool call, retry, and HITL
  interrupt traces with near-zero wiring, which matters given the multi-agent graph and the
  regeneration loops.
- **Phoenix (Arize)** is open-source, self-hostable, and stronger for **offline eval** of the
  generated content (accuracy of the verification agent, option-balance stats, grader
  calibration). Keep it pluggable so you can run eval suites there without moving tracing.

Implementation:
- A single `tracing.py` façade exposing `trace_span`, `log_metrics`, `log_eval` — backed by
  LangSmith by default, Phoenix via config flag.
- Trace IDs are also written to Postgres rows (`interactions`, `responses`, `check_runs`) so
  you can jump from a DB record to its trace.

What to instrument:
- Every agent call (model, tokens, latency, cost) — mirrored to `generation_metrics`.
- Every checker verdict and regeneration.
- Every learning response and score computation.
- HITL waits (clarification, cost gate) as spans, so time-to-approval is measurable.

---

## 4. Derived counts (for the curriculum / population page)

The curriculum page counts (`05 §8`, `07 §5`) are **derived from persisted rows**, not stored
denormalised (recompute on read, or maintain a materialised view refreshed on build):

| Count | Query source |
|-------|--------------|
| MCQs (per subtopic / course) | `interactions where type='mcq'` |
| Q&A items | `interactions where type='qa'` |
| Illustrations used (sourced vs generated) | `diagrams` grouped by `provenance` |
| Sources used (and by format) | `sources` grouped by `type` |
| Newest source date | `max(sources.published)` |
| Flagged / partially-sourced | `check_runs` verdicts + Auditor flags on `subtopics` |

---

## 5. Cost reconciliation storage

After the build, the Cost Reconciliation Agent (`03 §6b`) writes:
- `courses.cost_actual` — summed from `generation_metrics.cost` across all phases incl.
  retries, regens, and extra scout rounds.
- `courses.cost_delta_abs` / `cost_delta_pct` — actual vs `cost_estimate`.
- `courses.cost_reconciliation` — the `drivers[]` + human-readable `summary` explaining the
  delta.

Because every agent/tool call already writes to `generation_metrics`, actual cost is an
aggregation, not separate bookkeeping. The curriculum page shows estimate, actual, and delta
side by side with the reason.

**Cost-delta `.md` file (required).** In addition to the DB row, the reconciler writes a
human-readable **`.md`** under `./data/cost/<course_slug>-<id8>.md` (`courses.cost_md_path`)
capturing the reason **with context**: which course, estimated vs actual + delta, the per-phase
drivers/summary, and *how much actually ran* — web searches, scrapes, extractions, scout-again
rounds, generations, checks, reserve builds, sources used, subtopics built, interactions reused
from the library, and a token+cost-by-phase table. This makes each build's economics auditable
outside the app.

---

## 6. Session durability & token-free replay (testing iteration)

**Goal:** during the testing phase, a tester can leave application feedback, **restart the
application, and resume with all previously generated content and all session data intact —
without regenerating anything (no token spend).**

**How this is guaranteed:**
- **Generated content is immutable and fully persisted.** Once a course is built, all
  interactions, options, hints, content panels, and diagrams live in local Postgres (text +
  blobs). The learning
  runtime **reads** these; it never regenerates to serve an interaction. Replaying a course
  costs **zero** generation tokens.
- **Runtime LLM calls are cached/replayable.** The only runtime LLM calls are Q&A grading and
  light adaptive judgment. Cache grader outputs keyed by `(interaction_id, normalized_answer)`
  so re-running the same answer during testing doesn't re-spend. Adaptive decisions are rules
  where possible.
- **Sessions are checkpointed.** `sessions` + `responses` capture every step; the LangGraph
  session graph uses the Postgres checkpointer so an interrupted session **resumes at the exact
  step** after a restart.
- **Resume, never reset (required).** Opening a course's Learn screen **resumes the learner's
  most recent session** for that course (scoped by `user_id`) instead of creating a new one —
  so navigating away and back preserves both the position **and the running score**. A new
  session is created only when none exists. Creating a fresh session each visit (which silently
  zeroed the score) is a bug this rule exists to prevent. An **already-answered question is
  never re-scored**: submitting it again returns the existing state, and completed questions
  are viewable **read-only** (`07 §2`).
- **"Restart with content" action.** From any application-feedback context, a tester can
  restart the app / relaunch a session bound to the same `course_id` (and optionally the same
  `session_id` to resume, or a fresh session over the same built content). Either way, the
  build pipeline is **not** re-invoked.

**Rule:** the build graph and the session graph are separate for exactly this reason —
**iterating on UX/testing must never trigger a rebuild.** A rebuild happens only on an explicit
"rebuild course" action (e.g. after curriculum changes), and even then only changed subtopics
regenerate (idempotent regeneration, `02 §5`).

---

## 7. MCQ integrity invariant (content-feedback finding)

A tester reported an MCQ that showed **five** options (A–E) and, after answering, said *"the
answer was null."* Root cause: a generator drifted from the 4-option contract, and because the
correct-answer position could not be resolved the persisted `answer_key` was `null`, making the
item **unanswerable**. This must be structurally impossible:

- **Every persisted MCQ has exactly 4 options and a non-null `answer_key`.** The Option Checker
  (`03 §8`, `05 §7`) **repairs** structural drift deterministically before persistence —
  trimming extra options down to the flagged-correct one plus three distractors, padding when
  short, and always electing exactly one correct option — and persistence applies a final
  guard so a `null` `answer_key` can never be written.
- This is a hard invariant, enforced in code and covered by a regression test, not a
  best-effort check.

Content feedback (the `.md` tree, `§2`) is the primary signal for finding such defects; each
finding should map to either a spec change or an enforced invariant like this one.
