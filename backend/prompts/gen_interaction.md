You generate ONE interaction for an AI course, and you CHOOSE the interaction format that best
teaches this specific concept. Use ONLY the provided Content Package material. Ground examples
in the learner's domain where the topic allows.

Subtopic: "{subtopic_name}" — {description}
Difficulty (DL): {dl}   (DL1 easy, DL2 medium, DL3 hard)
Learner: orientation={orientation}, seniority={seniority}
Domain to frame examples in: {domain} (must_ground={must_ground})

Content Package (definitions, key claims, source excerpts):
{package}

Choose the SINGLE best format for THIS concept:
- "mcq" — a fact/understanding check with 4 options. Good default for conceptual ideas.
- "order" — arrange steps into the correct sequence. Use for PROCESSES / pipelines / ordered
  workflows (e.g. the steps of a request lifecycle).
- "blanks" — fill blanks in a sentence or code snippet from a word bank. Use to test precise
  TERMINOLOGY, key parameters, or small code fragments.
- "dragdrop" — drag entities into labelled boxes of an architecture diagram. Use for
  STRUCTURE / component roles / who-talks-to-whom relationships.

Every interaction (all formats) MUST include a personalized `content_panel_md` and a 3-rung
hint ladder: (1) general nudge that does NOT reveal the answer, (2) more specific, (3) reveals
the answer with a brief why.

Return ONLY JSON. Include `type`, `question_md`, `content_panel_md`, `hints`, and EXACTLY the
fields for the chosen type:

mcq:
{{ "type":"mcq", "question_md":"…", "content_panel_md":"…", "hints":["…","…","…"],
   "options":[{{"label":"A","text":"…","is_correct":false}}, …4 total, one correct… ] }}

order (3-6 steps; `correct_order` lists item ids in the right sequence):
{{ "type":"order", "question_md":"Put these steps in order:", "content_panel_md":"…",
   "hints":["…","…","…"],
   "items":[{{"id":"s1","text":"…"}}, …], "correct_order":["s3","s1","s2", …] }}

blanks (2-4 blanks; `segments` interleaves plain strings and {{"blank":"b1"}} markers; `bank`
holds the correct words PLUS 1-3 plausible distractors, all shuffled):
{{ "type":"blanks", "question_md":"Fill in the blanks:", "content_panel_md":"…",
   "hints":["…","…","…"],
   "segments":["The ", {{"blank":"b1"}}, " protocol exposes ", {{"blank":"b2"}}, "."],
   "blanks":[{{"id":"b1","answer":"MCP"}}, {{"id":"b2","answer":"tools"}}],
   "bank":["MCP","tools","REST","prompts"] }}

dragdrop (2-5 boxes; each box takes exactly one entity; `entities` includes 1-2 distractors;
`correct_mapping` maps box id → the correct entity id):
{{ "type":"dragdrop", "question_md":"Drag each component into the right box:",
   "content_panel_md":"…", "hints":["…","…","…"],
   "boxes":[{{"id":"box1","label":"Client"}}, {{"id":"box2","label":"Server"}}],
   "entities":[{{"id":"e1","text":"Host application"}}, {{"id":"e2","text":"Tool provider"}}, {{"id":"e3","text":"(distractor)"}}],
   "correct_mapping":{{"box1":"e1","box2":"e2"}} }}
