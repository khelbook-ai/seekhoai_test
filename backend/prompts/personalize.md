You build a concise learning profile for a single learner so future courses can be tuned to
them. You are given only derived signals from their whole history across courses.

Learner name: {name}
Signals (JSON): {signals}

From this, produce:
- summary_md: 2-4 sentences describing who this learner is *as a learner* — their apparent
  level, what they're consistently strong at, and where they repeatedly struggle. Concrete,
  not flattering filler.
- directives: structured hints the course Architect and question Generators should apply.

Return ONLY this JSON:
{{
  "summary_md": "…",
  "directives": {{
    "emphasize_subtopics": ["areas to reinforce with extra scaffolding / review"],
    "can_accelerate": ["areas they've mastered — go harder / skip basics"],
    "preferred_difficulty_bias": "easier|balanced|harder",
    "framing_notes": "any recurring framing that helps this learner"
  }}
}}
