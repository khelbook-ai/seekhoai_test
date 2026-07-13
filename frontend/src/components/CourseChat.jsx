import React, { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import ThumbsFeedback from "./ThumbsFeedback.jsx";

// In-course study assistant (spec 04 §9, 06 §10, 07 §2). ONE assistant per learner: it checks the
// current course's material, then answers with GLM 5.2 — free to go beyond the course when that
// gives a better answer. Every exchange is persisted, so the whole conversation (across ALL the
// learner's courses) is restored on refresh, each tagged with its course and timestamp.
const QUERY_MAX = 300;

function fmtTime(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }); }
  catch { return ""; }
}

export default function CourseChat({ sid }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [exchanges, setExchanges] = useState([]);   // {id, question, answer, course_name, created_at, sources, pending}
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const bodyRef = useRef(null);

  // Restore the learner's full assistant history (all courses) the first time the panel opens.
  useEffect(() => {
    if (!open || loaded) return;
    api.chatHistory().then((r) => { setExchanges(r.messages || []); setLoaded(true); })
      .catch(() => setLoaded(true));
  }, [open, loaded]);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [exchanges, busy, open]);

  async function send() {
    const query = q.trim().slice(0, QUERY_MAX);
    if (!query || busy) return;
    setQ(""); setBusy(true);
    const pending = { question: query, answer: null, created_at: new Date().toISOString(), pending: true };
    setExchanges((m) => [...m, pending]);
    try {
      const r = await api.chat(sid, query);
      setExchanges((m) => m.map((x) => x === pending
        ? { id: r.id, question: query, answer: r.answer, course_name: r.course_name,
            created_at: r.created_at || pending.created_at, sources: r.grounded ? r.sources : [] }
        : x));
    } catch (e) {
      setExchanges((m) => m.map((x) => x === pending
        ? { ...pending, answer: `Sorry — ${e.message}`, pending: false, error: true } : x));
    } finally { setBusy(false); }
  }

  if (!sid) return null;

  return (
    <div className={"coursechat" + (open ? " open" : "")}>
      {open ? (
        <div className="cc-panel">
          <div className="cc-head">
            <span>💬 Course assistant</span>
            <button className="cc-x" onClick={() => setOpen(false)} aria-label="Close">×</button>
          </div>
          <div className="cc-note">I check this course's material first, then answer as best I can —
            and I remember your questions across every course.</div>
          <div className="cc-body" ref={bodyRef}>
            {loaded && exchanges.length === 0 && (
              <div className="cc-empty">Ask me anything about what you're learning.</div>
            )}
            {!loaded && <div className="cc-empty"><span className="spin" /> loading your history…</div>}
            {exchanges.map((ex, i) => (
              <div key={ex.id || i} className="cc-ex">
                <div className="cc-ex-meta">
                  {ex.course_name ? <span className="cc-course">{ex.course_name}</span> : null}
                  <span>{ex.pending ? "now" : fmtTime(ex.created_at)}</span>
                </div>
                <div className="cc-msg you"><div className="cc-bubble">{ex.question}</div></div>
                {ex.pending ? (
                  <div className="cc-msg bot"><div className="cc-bubble"><span className="spin" /> thinking…</div></div>
                ) : (
                  <div className={"cc-msg bot" + (ex.error ? " err" : "")}>
                    <div className="cc-bubble">{ex.answer}</div>
                    {!ex.error && (
                      <div className="cc-meta">
                        {ex.sources?.length > 0 && <span className="cc-src">consulted: {ex.sources.join(", ")}</span>}
                        <ThumbsFeedback kind="chat" id={ex.id || sid} label="" compact />
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="cc-input">
            <textarea value={q} maxLength={QUERY_MAX} placeholder="Ask about this course…"
              onChange={(e) => setQ(e.target.value.slice(0, QUERY_MAX))}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
            <div className="cc-input-row">
              <span className={"cc-count" + (q.length >= QUERY_MAX ? " at-limit" : "")}>{q.length}/{QUERY_MAX}</span>
              <button className="btn" disabled={busy || !q.trim()} onClick={send}>Ask</button>
            </div>
          </div>
        </div>
      ) : (
        <button className="cc-fab" onClick={() => setOpen(true)}>💬 Ask about this course</button>
      )}
    </div>
  );
}
