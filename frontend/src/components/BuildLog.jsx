import React, { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

// Live technical build log (spec 07 §5). Shows tool use, MCP scraping, generation,
// checks and verification as they happen. Poll-based with an incremental cursor.
export default function BuildLog({ courseId, active }) {
  const [lines, setLines] = useState([]);
  const lastId = useRef(0);
  const box = useRef(null);

  useEffect(() => {
    let live = true;
    async function poll() {
      try {
        const d = await api.buildEvents(courseId, lastId.current);
        if (!live) return;
        if (d.events.length) {
          lastId.current = d.events[d.events.length - 1].id;
          setLines((prev) => [...prev, ...d.events]);
        }
      } catch {}
    }
    poll();
    const t = setInterval(poll, active ? 2500 : 10000);
    return () => { live = false; clearInterval(t); };
  }, [courseId, active]);

  useEffect(() => {
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [lines]);

  if (lines.length === 0) return null;
  return (
    <div className="buildlog" ref={box} aria-label="build log" aria-live="polite">
      {lines.map((e) => (
        <div className="ln" key={e.id}>
          <span className="ts">{fmtTime(e.at)}</span>
          <span className="ph">{e.phase}</span>
          <span className={"k-" + e.kind}>{e.message}</span>
        </div>
      ))}
    </div>
  );
}

// Local wall-clock timestamp for each build event (spec 07 §5).
function fmtTime(iso) {
  if (!iso) return "--:--:--";
  const d = new Date(iso);
  if (isNaN(d)) return "--:--:--";
  return d.toLocaleTimeString([], { hour12: false });
}
