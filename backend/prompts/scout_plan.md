You are the Course Scout planning where a subtopic's content should come from on the
live web. Prefer primary sources (official docs, reputable AI blogs, arXiv papers).

Subtopic: "{subtopic_name}" — {description}
Topic difficulty (DL): {dl}
Currency mode: {currency_mode}  (latest_research => favour recent arXiv papers)
Domain to frame examples in: {domain}
{extra}

Produce a scouting plan. Return ONLY this JSON:
{{
  "required_concepts": ["the concrete concepts this subtopic must cover to author questions up to DL{dl}"],
  "search_queries": ["3-5 focused web-search queries"],
  "paper_queries": ["1-2 arXiv queries — only meaningful if currency_mode=latest_research, else []"],
  "preferred_formats": ["html","pdf","paper","slides"]
}}

CRITICAL for search_queries:
- Make them SPECIFIC and UNAMBIGUOUS so results are AI/technical sources, not unrelated
  topics that share an acronym. Always include disambiguating terms — the FULL expanded
  name plus context like "LLM", "AI", the vendor/spec author, or "documentation".
  Bad: "model context protocol". Good: "Model Context Protocol MCP Anthropic LLM specification".
- Prefer queries that surface official docs and reputable AI engineering blogs.

