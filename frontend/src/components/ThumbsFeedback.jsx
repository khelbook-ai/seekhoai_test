import React, { useState } from "react";
import { api } from "../api.js";

// One-click thumbs up/down (spec 06 §8, 07). Drop it anywhere a learner might have an opinion:
// a question, its content/hint panels, the answer feedback, a whole course, a page. Voting is
// optimistic and idempotent — re-clicking the same thumb clears it, the other flips it. An
// optional inline note lets the learner say *why* without leaving the flow.
//   <ThumbsFeedback kind="interaction" id={it.id} label="Was this question useful?" />
export default function ThumbsFeedback({ kind, id = "", label = "Helpful?", compact = false }) {
  const [value, setValue] = useState(0);      // 1 up, -1 down, 0 none
  const [noteOpen, setNoteOpen] = useState(false);
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState(false);

  async function vote(v) {
    const next = value === v ? 0 : v;   // toggle off if same thumb
    setValue(next);
    setErr(false);
    if (next === 0) return;             // toggling off is local-only; nothing to record
    setNoteOpen(next === -1 && !compact);   // invite a reason on a thumbs-down
    try { await api.reaction(kind, id, next, null); setSaved(true); }
    catch { setErr(true); }
  }
  async function sendNote() {
    try { await api.reaction(kind, id, value || -1, note); setNoteOpen(false); setSaved(true); }
    catch { setErr(true); }
  }

  return (
    <div className={"thumbs" + (compact ? " compact" : "")}>
      {!compact && <span className="thumbs-label">{label}</span>}
      <button className={"thumb" + (value === 1 ? " on up" : "")} title="Helpful"
        aria-pressed={value === 1} onClick={() => vote(1)}>👍</button>
      <button className={"thumb" + (value === -1 ? " on down" : "")} title="Not helpful"
        aria-pressed={value === -1} onClick={() => vote(-1)}>👎</button>
      {saved && !noteOpen && <span className="thumbs-msg">{err ? "couldn't save" : "thanks!"}</span>}
      {noteOpen && (
        <span className="thumbs-note">
          <input className="text" placeholder="what went wrong? (optional)" value={note}
            autoFocus onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendNote()} />
          <button className="btn secondary" onClick={sendNote}>Send</button>
        </span>
      )}
    </div>
  );
}
