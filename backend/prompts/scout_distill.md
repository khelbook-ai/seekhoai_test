You distill scouted source material into a Content Package for a subtopic. Work ONLY
from the provided extracted text — do not add outside knowledge. Attribute every claim
and definition to a source_id from the list.

Subtopic: "{subtopic_name}" — {description}
Required concepts: {required_concepts}

Extracted material (source_id => text):
{material}

Return ONLY this JSON:
{{
  "key_claims": [{{"text": "a factual claim from the sources", "source_id": "...", "confidence": 0.0-1.0}}],
  "definitions": [{{"term": "...", "definition": "...", "source_id": "..."}}],
  "covered_concepts": ["which required_concepts the material actually covers"],
  "gaps": ["required_concepts NOT covered by the material"]
}}
Extract 5-12 key claims and 3-8 definitions. If the material is thin, return fewer and
list the missing concepts in gaps.
