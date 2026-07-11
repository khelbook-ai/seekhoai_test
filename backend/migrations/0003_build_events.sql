-- Build-event log (spec 05 §9, 07 §5): a technical, tester-facing trace of what the
-- build pipeline is doing (tool use, MCP scraping, generation, checks). New file;
-- earlier migrations are never edited.
CREATE TABLE IF NOT EXISTS build_events (
  id          bigserial PRIMARY KEY,
  course_id   uuid REFERENCES courses(id),
  phase       text,                              -- intake|scouting|generation|checking|verification|persist|cost
  kind        text,                              -- web_search|scrape|extract|mcp|audit|generate|check|verify|warn|info|...
  message     text,
  meta        jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_build_events_course ON build_events(course_id, id);
