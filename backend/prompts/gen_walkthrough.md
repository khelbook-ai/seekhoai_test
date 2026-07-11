You create a GUIDED CODE WALKTHROUGH for a technical learner: a small, realistic code example
plus a sequence of concept steps that each highlight the relevant lines. Then a short MCQ that
tests understanding of the code. Ground everything in the provided material.

Subtopic: "{subtopic_name}" — {description}
Difficulty (DL): {dl}
Learner: orientation=technical, seniority={seniority}
Domain to frame examples in: {domain} (must_ground={must_ground})

Content Package (definitions, key claims, source excerpts):
{package}

Rules:
- Write **idiomatic, correct, self-contained** code that illustrates this subtopic (like a real
  example a developer would read). Prefer one primary file; add 1-2 small supporting files only
  if they genuinely help (e.g. client.py). Keep each file under ~40 lines.
- `content` for each file is the FULL file text with real newlines. Line numbers are 1-indexed.
- Produce 4-6 **steps**. Each step teaches one idea and highlights the exact line range(s) that
  illustrate it. `highlight` is a list of [start_line, end_line] inclusive ranges within that
  step's file. Ranges MUST be valid line numbers for that file. Steps should progress in reading
  order and may switch files.
- Finish with ONE multiple-choice question (exactly 4 options, one correct) that checks whether
  the learner understood how the code works — reference the code, not trivia.

Return ONLY this JSON:
{{
  "title": "short walkthrough title",
  "files": [
    {{"name": "server.py", "language": "python", "content": "full file text with \\n newlines"}}
  ],
  "steps": [
    {{"title": "1. …", "concept_md": "what this shows, 1-2 sentences",
      "file": "server.py", "highlight": [[14, 22]]}}
  ],
  "mcq": {{
    "question_md": "a question about the code above",
    "options": [
      {{"label": "A", "text": "…", "is_correct": false}},
      {{"label": "B", "text": "…", "is_correct": true}},
      {{"label": "C", "text": "…", "is_correct": false}},
      {{"label": "D", "text": "…", "is_correct": false}}
    ],
    "content_panel_md": "brief explanation for this question",
    "hints": ["general nudge (no answer)", "more specific", "reveals the answer with a brief why"]
  }}
}}
