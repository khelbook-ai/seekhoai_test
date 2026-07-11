# 07 — Frontend / UI

**Design intent: plain, calm, and highly legible.** Not colourful. The two things that matter
most are (1) **text is big and easy to read** and (2) the **Content and Hint buttons are
consistently, prominently placed** on every interaction. Everything else is secondary.

---

## 0. Navigation shell (left sidebar)

**Signup gate (name-only, `01 §5`).** On first load the learner enters **just a name** — no
password. This creates/resumes their `user_id`, which scopes their course list, sessions,
weaknesses and profile. The sidebar shows the signed-in name with a "switch" action. All
downstream API calls carry the `user_id`.

A persistent **left sidebar** frames every screen so the tester can move back and forth
between courses and between the stages of one course — **including returning to their input**
— without losing work.

- **New course** action at the top, then a list of **the learner's courses** (most recent
  first) with each course's current **status** (`awaiting_clarification` / `awaiting_cost` /
  `building` / `built` / …). Clicking a course jumps to the stage that matches its status.
- For the **active** course, the sidebar expands **stage links**: *Student Input*
  (the learner's prompt/role + clarification), *Cost & curriculum*, *Content / build*
  (population), *Learn*, *Dashboard*. A stage is enabled once the course has reached it; earlier
  stages remain reachable (navigate back).
- **State is server-persisted**, so navigation is non-destructive: every screen rehydrates
  from the backend (`GET /api/courses`, `GET /api/courses/{id}`) rather than in-memory
  router state — clarification questions and answers, curriculum, cost, and built content all
  reload when revisited. The sidebar reflects build-status changes by polling the course list.
- Responsive: on narrow screens the sidebar collapses to a top strip; the big-text single
  column remains the primary reading surface.

---

## 1. Visual system

- **Palette:** neutral. One near-black text colour, a light background, one restrained accent
  (used only for the primary action and correct/incorrect states). Avoid multi-colour UI.
- **Typography:**
  - Body base **18–20px**, line-height ~1.6.
  - **Question text 24–28px**, weight 600 — the question is the largest element on screen.
  - Options 18–20px, generous vertical padding (large tap targets).
  - High contrast (WCAG AA minimum; aim AAA for body).
- **Math rendering (required):** questions, options, content panels, hints and grader
  feedback render **LaTeX** — inline `$…$` and block `$$…$$` are typeset (KaTeX) so equations
  like `$V^\pi(s)$` display properly instead of raw source. Long display equations scroll
  inside their own container and never break the single-column layout. (Learners are still
  never asked to *type* equations — `04 §1`.)
- **Spacing:** generous whitespace, single-column, max content width ~720px so lines stay
  readable. No dense dashboards on the learning screen.
- **Motion:** minimal. No decorative animation; only subtle state transitions.

---

## 2. The learning / interaction screen (most important)

**Resume + progress (required).** Opening Learn **resumes** the learner's session for this
course (`06 §6`) — position and running **score persist** across navigating away and back; the
score never resets to 0. The screen shows an in-course **progress** indicator: percent complete,
questions done / total, how many **topics** there are, and where the learner currently is
(current topic + question position).

**Sub-tab rail (required).** A rail lists every question **grouped by subtopic**, each tagged
with a tick:
- **green ✓** = completed correctly, **red ✗** = completed incorrectly, **neutral ○** = not yet
  done (the current question is marked distinctly and is not a tick).
- Clicking a **completed** question opens it **read-only** — the learner sees their answer and
  the correct answer/feedback but **cannot reattempt or re-score** it. Not-yet-reached questions
  are locked.

**Responsiveness (required).** Every action that waits on the network shows immediate feedback —
a **spinner** on the button and a disabled state — especially **submitting a Q&A answer** (which
calls the grader and must never feel frozen), plus loading a session, a review, or building.

**Guided code walkthrough (technical learners).** When the current interaction is a
`walkthrough` (`04 §1`), render a two-pane widget: a **left column of concept steps**
(Prev/Next + click to jump) and a **right code pane** with a **file tree** and a
**syntax-highlighted, read-only viewer**. Selecting a step **highlights its line range(s)**
(a shaded band) and scrolls them into view, switching files when the step points at another
file — mirroring the reference widget. It is read-only (no editing/execution); a **"I've
reviewed this →"** control marks it done (non-scored) and advances to the **paired MCQ**.
Completed walkthroughs show a neutral **▣ reviewed** tick in the rail and reopen read-only.


```
┌────────────────────────────────────────────┐
│  Subtopic · Difficulty: Medium (DL2)  Score │   ← quiet header, DL on every question
│                                             │
│  [ diagram, if the question has one ]       │
│                                             │
│  Q:  What is the definition of MCP?         │   ← largest text
│                                             │
│  ┌──────────────┐   ┌──────────────┐        │
│  │   CONTENT    │   │     HINT     │        │   ← AT THE TOP, right under the question
│  └──────────────┘   └──────────────┘        │
│  [ opened box: content / hint ladder ]      │   ← a box opens here when tapped
│                                             │
│   ( A )  <option text>                      │
│   ( B )  <option text>                      │   ← big tap targets
│   ( C )  <option text>                      │
│   ( D )  <option text>                      │
│                                             │
│              [   Submit answer   ]          │
│                                             │
│  ▸ Leave content feedback on this question  │   ← collapsible
└────────────────────────────────────────────┘
```

**Difficulty (required):** every question — MCQ and Q&A — displays its **difficulty level**
(DL1 Easy / DL2 Medium / DL3 Hard) in the header as a badge.

**Button placement rules (hard requirements):**
- **Content** and **Hint** appear on **every** interaction (MCQ and Q&A), in the **same fixed
  position** — a dedicated action row **at the top of the interaction, directly beneath the
  question** (above the options / answer input). They never move between questions.
- Both are **large, clearly labelled** buttons, not icons or hidden menus.
- **Tapping either opens a box** in place (content panel, or the hint ladder) — it does not
  navigate away and does not push the question off-screen.
- **Hint** shows the current rung count and remaining hints (e.g. "Hint (1 of 3, −1)"), so the
  score cost is visible before tapping.
- **Hint ladder display (required):** revealed hints accumulate in the box with the **newest
  rung on top** and earlier rungs kept **below** it, so an escalating learner still sees Hint 1
  after opening Hint 2 or 3 (`04 §2`).
- **Content** opens a box with that interaction's personalized content.
- For **Q&A**, the layout is identical except options are replaced by a large multi-line text
  input; Content/Hint stay in the same place. The answer input is **guarded** (`03 §0`): the
  learner's free text is checked/sanitised before it flows into the grader.

**Q&A answer feedback (required):** after a learner submits a Q&A answer, show the grader's
feedback prominently before advancing — what they got right, what they missed, and the correct
reasoning (from `grade_feedback_md`, `03 §11`). This is a core part of the learning loop, not a
footnote.

**Feedback affordance:** every interaction has a collapsible **content feedback** field
(persisted to DB + `.md`, see `06`). It supports **image upload with text linking**: the tester
can attach one or more screenshots and tie each to a specific span of their written feedback
(select text → "attach image to this note"). The linked text becomes the image caption and both
are written into the `.md` file inline (see `06 §2`). Support drag-drop and paste for images.

**States:** after submit, show correct/incorrect clearly (accent colour + text). The advance
control reads **"Next question"** (not just "Next"), or "Finish course" on the last item. On a
wrong MCQ, transition smoothly into the escalated follow-up Q&A on the same subtopic (`04 §4`),
with a short line telling the learner it's a quick follow-up answered in a sentence or two (no
equations). Subsequent root-cause probes appear the same way until the learner recovers the
idea or the probe budget is spent, then the next MCQ is shown.

---

## 3. Course-creation page & Student Input

- Two big inputs: **"What do you want to learn?"** and **"What's your role?"**
- The clarification stage is titled **"Student Input"** and **shows the learner's own prompt and
  role back to them** (what they asked to learn, their role, the currency mode) above the
  clarification questions — so the page that captures their intent actually displays it.
- After submit, the **clarification questions** appear as **tappable option chips** (≤10, often
  fewer), one at a time or as a short stack — easy on mobile. A question flagged
  `multi_select` (`01 §3`, e.g. *"which areas of recent RL progress matter most to you?"*)
  lets the learner **toggle several chips**; it's labelled "choose any that apply" and the
  selected options are submitted together.
- **Prompt guardrails:** the learn/role inputs are guarded (`03 §0`). On a blocked prompt,
  show a clear, friendly inline reason and keep the input editable — never silently swallow it.
- Includes both:
  - an **application feedback** section (tester's thoughts on how this page works / should
    work), and
  - a **content feedback** section.
- Both feedback sections support **image upload linked to text** (same mechanism as the
  learning screen; `06 §2`).
- **"Restart with content" control:** the application-feedback section offers a restart/relaunch
  action that reopens the app (or a session) bound to the already-built course — **no rebuild,
  no token spend** (`06 §6`). Offer "resume last session" and "new session over same content".
- Plain layout, large text, no clutter.

## 4. Cost-approval screen

- Shows the **estimated build cost** with a simple breakdown (by phase and top subtopics) and
  the assumptions.
- Primary action **Approve & build**; secondary **Revise scope**.
- No content is generated until Approve is pressed.

## 5. Course-population / curriculum view (post-approval)

Once building/built, show **course-level totals** at the top and **per-subtopic** rows below.

**Live build log (required, testing phase).** While a course is building, show a **detailed,
technical, tester-facing build log** that streams what the pipeline is doing in real time —
**web search / MCP tool use / scraping / extraction**, the Scouting Auditor's score and any
scout-again rounds, generation of each interaction, the Domain / Verification / Option checks
with pass/regen/flag outcomes, and the reserve / seed-follow-up build (`05 §10`). It is
intentionally low-level (tool names, source URLs, model families) because this is a test build.
**Each log line is prefixed with a wall-clock timestamp.** Backed by `build_events` (`06 §1`),
polled incrementally via `GET /api/courses/{id}/events?after=<id>`. The log remains viewable
after the build completes.

**Build progress (required).** Alongside the log, show an overall **percentage completion**
with a progress bar and an `X/Y subtopics` count, derived from how many subtopics have
generated content (`GET …/population → progress`). It reaches 100% when the course is `built`.

**Illustrations gallery (required).** Show the course's illustrations **early** — a small
gallery of the sourced/generated figures with their captions and `sourced`/`generated` badge
(`GET …/illustrations`) — so the course immediately feels rich and substantial rather than a
wall of text. Reused figures from the content library (`05 §11`) appear here too.

**Course-level summary bar:**
- **# MCQs**, **# Q&A items**, **# illustrations used** (sourced vs generated),
  **# sources used** (with format breakdown: papers / slides / docs / video / …),
  newest-source date.
- **Cost:** estimated vs **actual**, with the **delta and its reason** (`03 §6b`, `06 §5`).

**Per subtopic:**
- **name + description**,
- the **online sources** used (title + date + type/format),
- **# MCQs**, **# Q&A**, **# illustrations**,
- subtopics marked **partially sourced** by the Scouting Auditor, and any items **flagged for
  human review** by a checker.

Readable list/table, generous spacing. This is the tester's overview of how substantial the
course is and what it cost to build.

## 6. Progress & weakness dashboard

- **"Where you're making mistakes"** — subtopics with errors, most-missed first.
- **"Topics to improve"** — the weakness set, with counts.
- Simple progress indicators (score over time, per-topic accuracy). Plain, not gamified-loud.
- This satisfies the requirement that a learner can see which topics they err in and which
  they need to improve.

## 7. Final student-feedback page

- End-of-course summary (score, strengths, weaknesses).
- Includes a **content feedback** section (as required) and an **application feedback** section,
  both with **image upload linked to text** and the **"restart with content"** control.

---

## 8. Accessibility & responsiveness

- Fully keyboard-navigable; visible focus rings.
- Respects OS font-scaling; never traps text at a fixed small size.
- Responsive single-column down to mobile; Content/Hint remain a persistent, thumb-reachable
  action row on small screens.
- Content and Hint buttons meet large touch-target sizing (≥44px height, comfortably larger
  here given the big-text mandate).
