You generate one high-quality multiple-choice interaction for an AI course, using ONLY
the provided Content Package material. Ground every example, scenario, and phrasing in
the learner's domain where the topic allows.

Subtopic: "{subtopic_name}" — {description}
Difficulty (DL): {dl}   (DL1 easy, DL2 medium, DL3 hard)
Learner: orientation={orientation}, seniority={seniority}
Domain to frame examples in: {domain} (must_ground={must_ground})
{definition_note}

Content Package (definitions, key claims, source excerpts):
{package}

Requirements:
- Exactly 4 options; exactly one correct. Options are TEXT ONLY (no diagrams).
- Distractors must be plausible and mutually exclusive.
- LENGTH BALANCE (critical): all four options must be comparable in length. The correct
  option must NOT be the longest choice — that is a dead give-away. Write each distractor
  with the same level of detail and roughly the same character count as the correct option
  (add plausible qualifiers/specifics to short distractors rather than trimming the correct
  one). A deterministic checker measures each option's length and will send the item back
  for regeneration if the correct option is the longest.
- REGISTER PARITY (critical): the correct option must NOT be the most technically-worded /
  precise / "textbook-sounding" choice. A learner should not be able to pick the answer just
  by choosing the one that "sounds the most sophisticated." Give the distractors the SAME
  technical register, jargon density, and specificity as the correct answer — each wrong
  option must read like a confident, expert-sounding definition that is nonetheless factually
  wrong (wrong mechanism, wrong scope, subtly wrong detail). Avoid distractors that are
  obviously naive, vague, or under-specified relative to the correct one.
- The content panel is a personalized "how it works / what it is" explanation for THIS
  question and persona — not a generic dump.
- Three escalating hints: (1) general nudge that does NOT reveal the answer,
  (2) more specific, (3) reveals the correct answer with a brief why.

Return ONLY this JSON:
{{
  "question_md": "the question (markdown; may reference a diagram if one clearly helps)",
  "options": [
    {{"label": "A", "text": "...", "is_correct": false}},
    {{"label": "B", "text": "...", "is_correct": true}},
    {{"label": "C", "text": "...", "is_correct": false}},
    {{"label": "D", "text": "...", "is_correct": false}}
  ],
  "content_panel_md": "personalized explanation",
  "hints": ["hint 1", "hint 2", "hint 3 (reveals answer)"],
  "diagram_suggestion": {{"needed": true|false, "what": "what the diagram should show"}}
}}
