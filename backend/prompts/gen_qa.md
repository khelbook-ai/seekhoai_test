You generate one free-response (Q&A) interaction for an AI course, using ONLY the
provided Content Package material. Ground examples in the learner's domain where the
topic allows.

Subtopic: "{subtopic_name}" — {description}
Difficulty (DL): {dl}
Learner: orientation={orientation}, seniority={seniority}
Domain to frame examples in: {domain} (must_ground={must_ground})

Content Package (definitions, key claims, source excerpts):
{package}

Requirements:
- A gradable question with a rubric of key points and weights (sums to ~1.0).
- A personalized content panel for THIS question and persona.
- Three escalating hints: (1) general nudge (no answer), (2) more specific,
  (3) reveals the expected answer with a brief why.

Return ONLY this JSON:
{{
  "question_md": "the open question (markdown)",
  "qa_rubric": {{
    "key_points": [{{"point": "...", "weight": 0.4}}, {{"point": "...", "weight": 0.3}}],
    "model_answer": "a concise correct answer for grading reference"
  }},
  "content_panel_md": "personalized explanation",
  "hints": ["hint 1", "hint 2", "hint 3 (reveals expected answer)"],
  "diagram_suggestion": {{"needed": true|false, "what": "what the diagram should show"}}
}}
