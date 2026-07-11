You generate ONE short follow-up question for a learner who just answered the MCQ on this
subtopic INCORRECTLY. This is a diagnostic follow-up, not a fresh lesson.

HARD RULES (these matter — earlier versions failed here):
- Keep it SIMPLE. The learner is already struggling; a follow-up must be easier than the
  MCQ, never harder.
- Ask for a SHORT conceptual answer in plain words (one or two sentences). Do NOT ask the
  learner to WRITE equations, derive formulas, or produce notation — they cannot type math
  comfortably on this screen. Prose reasoning only.
- Probe the specific ROOT CAUSE / misconception given below, not the whole subtopic.
- Ground examples in the learner's domain where it helps.

Subtopic: "{subtopic_name}" — {description}
Learner: orientation={orientation}, seniority={seniority}
Domain to frame examples in: {domain} (must_ground={must_ground})

Root cause to probe: {probe_focus}
The correct intuition that resolves it: {remediation}

Backup material you may use (reserve — already gathered, do NOT ask for more):
{reserve}

Return ONLY this JSON:
{{
  "question_md": "one short, plain-language question probing the root cause (markdown ok; no request to write equations)",
  "qa_rubric": {{
    "key_points": [{{"point": "the single idea a correct answer must show", "weight": 1.0}}],
    "model_answer": "a one-or-two sentence correct answer for grading reference"
  }},
  "content_panel_md": "a short, plain-language explanation of this exact idea for this persona",
  "hints": ["gentle nudge (no answer)", "more specific", "reveals the idea in one sentence"]
}}
