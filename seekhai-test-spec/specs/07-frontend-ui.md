# 07 — Frontend / UI

**Design intent: plain, calm, and highly legible.** Not colourful. The two things that matter
most are (1) **text is big and easy to read** and (2) the **Content and Hint buttons are
consistently, prominently placed** on every interaction. Everything else is secondary.

---

## 1. Visual system

- **Palette:** neutral. One near-black text colour, a light background, one restrained accent
  (used only for the primary action and correct/incorrect states). Avoid multi-colour UI.
- **Typography:**
  - Body base **18–20px**, line-height ~1.6.
  - **Question text 24–28px**, weight 600 — the question is the largest element on screen.
  - Options 18–20px, generous vertical padding (large tap targets).
  - High contrast (WCAG AA minimum; aim AAA for body).
- **Spacing:** generous whitespace, single-column, max content width ~720px so lines stay
  readable. No dense dashboards on the learning screen.
- **Motion:** minimal. No decorative animation; only subtle state transitions.

---

## 2. The learning / interaction screen (most important)

```
┌────────────────────────────────────────────┐
│  Course · Subtopic            Score: 24     │   ← quiet header
│                                             │
│  [ diagram, if the question has one ]       │
│                                             │
│  Q:  What is the definition of MCP?         │   ← largest text
│                                             │
│   ( A )  <option text>                      │
│   ( B )  <option text>                      │   ← big tap targets
│   ( C )  <option text>                      │
│   ( D )  <option text>                      │
│                                             │
│  ┌──────────────┐   ┌──────────────┐        │
│  │   CONTENT    │   │     HINT     │        │   ← ALWAYS here, always visible
│  └──────────────┘   └──────────────┘        │
│                                             │
│              [   Submit answer   ]          │
│                                             │
│  ▸ Leave content feedback on this question  │   ← collapsible
└────────────────────────────────────────────┘
```

**Button placement rules (hard requirements):**
- **Content** and **Hint** appear on **every** interaction (MCQ and Q&A), in the **same fixed
  position** — a dedicated action row directly beneath the question/options and **above**
  Submit. They never move between questions.
- Both are **large, clearly labelled** buttons, not icons or hidden menus.
- **Hint** shows the current rung count and remaining hints (e.g. "Hint (1 of 3, −1)"), so the
  score cost is visible before tapping.
- **Content** opens a panel/drawer with that interaction's personalized content; it does not
  navigate away.
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

**States:** after submit, show correct/incorrect clearly (accent colour + text). On a wrong
MCQ, transition smoothly into the escalated Q&A on the same subtopic.

---

## 3. Course-creation page

- Two big inputs: **"What do you want to learn?"** and **"What's your role?"**
- After submit, the **clarification questions** appear as **tappable option chips** (≤10, often
  fewer), one at a time or as a short stack — easy on mobile.
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
