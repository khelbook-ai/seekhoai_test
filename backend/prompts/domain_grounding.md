You infer the CONTENT DOMAIN the learning material should be framed in — the concrete
world its examples, MCQ scenarios, and Q&A prompts should come from. This is distinct
from the topic. Example: role "VP of AmEx", topic "how LLMs work" → domain "American
Express / credit cards / payments / financial services".

Learner role: "{raw_role}"
Learner prompt: "{raw_prompt}"
Orientation: {orientation}

Return ONLY this JSON:
{{
  "domain": "the concrete domain, or 'general' if the role implies no specific world",
  "example_entities": ["concrete entities examples should use, e.g. 'fraud detection'"],
  "framing": "technical|business|general",
  "must_ground": true|false,
  "confidence": 0.0-1.0
}}
Set must_ground=false (domain "general") for a plain student/hobbyist with no domain.
Set must_ground=true when the role clearly implies a specific industry/company/domain.
