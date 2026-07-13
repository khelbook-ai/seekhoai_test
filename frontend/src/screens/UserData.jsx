import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import MarkdownView from "../components/MarkdownView.jsx";
import ThumbsFeedback from "../components/ThumbsFeedback.jsx";
import AppFeedback from "../components/AppFeedback.jsx";

// User-level DB view (spec 06 §9, 07). Everything we hold about this learner in one place:
// their name, then per course — the prompt they entered, their answers to the preference
// questions, every question asked + their response, and the end-to-end token cost of that
// course (scouting + creation + Q&A feedback). The most recent active course's cost is
// surfaced at the top (spec item 4).
const money = (n) => (n == null ? "—" : n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`);
const tokens = (n) => (n == null ? "—" : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`);

export default function UserData() {
  const nav = useNavigate();
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => { api.dossier().then(setD).catch((e) => setErr(e.message)); }, []);

  if (err) return <div className="wrap"><p className="err">{err}</p></div>;
  if (!d) return <div className="wrap"><p className="spinner"><span className="spin" /> Loading your record…</p></div>;

  const last = d.courses.find((c) => c.course_id === d.last_completed_course_id);

  return (
    <div className="wrap dossier">
      <h1 className="title">{d.name}'s learning record</h1>
      <p className="lead">One place for everything Seekhai has captured about your learning —
        every course, the prompt you gave, your preferences, your answers, and what it cost to build.</p>

      <div className="u-card">
        <div className="io-row"><span className="io-k">User</span><span className="io-v">{d.name}</span></div>
        <div className="io-row"><span className="io-k">User ID</span><span className="io-v mono">{d.user_id}</span></div>
        <div className="io-row"><span className="io-k">Courses</span><span className="io-v">{d.course_count}</span></div>
        <div className="io-row"><span className="io-k">Member since</span>
          <span className="io-v">{d.created_at ? new Date(d.created_at).toLocaleDateString() : "—"}</span></div>
      </div>

      {last && (
        <div className="u-card spend">
          <h2 className="sub" style={{ marginTop: 0 }}>Last course — end-to-end token cost</h2>
          <p className="note" style={{ marginTop: 0 }}>{last.title || "Untitled"} — everything it took to
            research, build and run this course.</p>
          <CostGrid cost={last.cost} />
        </div>
      )}

      <h2 className="sub">Every course, prompt, preference &amp; answer</h2>
      {d.courses.length === 0 && <p className="note">No courses yet. <button className="link" onClick={() => nav("/")}>Build one →</button></p>}

      {d.courses.map((c, i) => (
        <details key={c.course_id} className="d-course" open={i === 0}>
          <summary>
            <span>{c.title || "Untitled course"}</span>
            <span className="st">{c.status} · {money(c.cost?.total)}</span>
          </summary>
          <div className="d-body">
            <div className="io-row"><span className="io-k">Course ID</span><span className="io-v mono">{c.course_id}</span></div>
            <div className="io-row"><span className="io-k">Prompt</span><span className="io-v">{c.raw_prompt || "—"}</span></div>
            <div className="io-row"><span className="io-k">Mode</span><span className="io-v">{c.currency_mode || "—"}</span></div>

            <h3 style={{ margin: "16px 0 6px" }}>End-to-end token cost</h3>
            <CostGrid cost={c.cost} />

            {c.preferences.length > 0 && <>
              <h3 style={{ margin: "18px 0 4px" }}>Your preference answers</h3>
              {c.preferences.map((p, k) => (
                <div key={k} className="pref-row">
                  <div className="q">{p.question}</div>
                  <div className="a">{p.answer || "(no answer)"}</div>
                </div>
              ))}
            </>}

            <h3 style={{ margin: "18px 0 4px" }}>Questions asked &amp; your responses ({c.questions.length})</h3>
            {c.questions.length === 0 ? <p className="note">Not attempted yet.</p> : (
              <div style={{ overflowX: "auto" }}>
                <table className="qa-log">
                  <thead><tr><th>#</th><th>Type</th><th>DL</th><th>Question</th><th>Your answer</th><th>Result</th></tr></thead>
                  <tbody>
                    {c.questions.map((q, k) => (
                      <tr key={k}>
                        <td className="mono">{k + 1}</td>
                        <td>{q.type}{q.role && q.role !== "main" ? " ↳" : ""}</td>
                        <td className="mono">DL{q.dl}</td>
                        <td><MarkdownView>{(q.question_md || "").slice(0, 240)}</MarkdownView></td>
                        <td>{q.your_answer || "—"}</td>
                        <td className={"res " + (q.is_correct ? "correct" : q.is_correct === false ? "wrong" : "")}>
                          {q.band ? q.band : q.is_correct == null ? "—" : q.is_correct ? "✓ correct" : "✗ wrong"}
                          {q.score_awarded != null && <span className="note"> · +{q.score_awarded}</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="thumbs-bar">
              <ThumbsFeedback kind="course" id={c.course_id} label="Was this course worthwhile?" />
            </div>
          </div>
        </details>
      ))}

      <div style={{ marginTop: 32 }}>
        <AppFeedback pageKey="user_data" />
      </div>
    </div>
  );
}

function CostGrid({ cost }) {
  if (!cost) return <p className="note">No cost recorded yet.</p>;
  const b = cost.buckets || {};
  return (
    <>
      <div className="cost-grid">
        <div className="stat"><div className="k">Total</div><div className="v">{money(cost.total)}</div></div>
        <div className="stat"><div className="k">Content scouting</div><div className="v">{money(b.scouting)}</div></div>
        <div className="stat"><div className="k">Content creation</div><div className="v">{money(b.creation)}</div></div>
        <div className="stat"><div className="k">Q&amp;A feedback</div><div className="v">{money(b.qa_feedback)}</div></div>
      </div>
      <p className="note">{tokens(cost.tokens_in)} tokens in · {tokens(cost.tokens_out)} tokens out ·
        {" "}{cost.calls} model call(s){b.other ? ` · ${money(b.other)} other` : ""}</p>
    </>
  );
}
