import React, { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import AppFeedback from "../components/AppFeedback.jsx";
import ThumbsFeedback from "../components/ThumbsFeedback.jsx";

// Progress & weakness dashboard + final feedback page (spec 07 §6/§7).
export default function Dashboard() {
  const { courseId } = useParams();
  const nav = useNavigate();
  const sid = useSearchParams()[0].get("session");
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [msg, setMsg] = useState(null);

  useEffect(() => { api.dashboard(courseId, sid).then(setD).catch((e) => setErr(e.message)); }, [courseId, sid]);

  async function restart(mode) {
    const r = await api.restart(courseId, mode);
    setMsg(`${mode === "resume" ? "Resumed" : "Fresh"} session — no rebuild, no token spend.`);
    nav(`/learn/${courseId}`);
  }

  if (err) return <div className="wrap"><p className="err">{err}</p></div>;
  if (!d) return <div className="wrap"><p className="spinner">Loading…</p></div>;

  const maxScore = Math.max(...(d.score_series.length ? d.score_series : [1]));

  return (
    <div className="wrap">
      <h1 className="title">{d.title}</h1>
      <p className="lead">Total score across this course: <strong>{d.total_score}</strong></p>

      <div className="thumbs-bar" style={{ marginTop: 0 }}>
        <ThumbsFeedback kind="course" id={courseId} label="How was this course overall?" />
      </div>

      <h2 className="sub">Where you're making mistakes</h2>
      {d.weaknesses.length === 0 ? <p className="note">No weaknesses recorded yet.</p> : (
        <table className="grid">
          <thead><tr><th>Subtopic</th><th>Topic</th><th>Errors</th></tr></thead>
          <tbody>
            {d.weaknesses.map((w, i) => (
              <tr key={i}><td>{w.subtopic}</td><td>{w.topic}</td><td className="mono">{w.error_count}</td></tr>
            ))}
          </tbody>
        </table>
      )}

      <h2 className="sub">Topics to improve / accuracy</h2>
      {d.accuracy.map((a, i) => (
        <div key={i} style={{ margin: "10px 0" }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span>{a.subtopic} <span className="note">({a.topic})</span></span>
            <span className="mono">{a.correct}/{a.attempts} · {a.pct}%</span>
          </div>
          <div className="bar"><span style={{ width: `${a.pct}%` }} /></div>
        </div>
      ))}

      {d.score_series.length > 0 && (
        <>
          <h2 className="sub">Score over the session</h2>
          <div className="row" style={{ alignItems: "flex-end", height: 80, gap: 4 }}>
            {d.score_series.map((s, i) => (
              <div key={i} title={`${s}`} style={{
                flex: 1, background: "var(--accent)", borderRadius: 3,
                height: `${(s / maxScore) * 100}%`, minHeight: 3
              }} />
            ))}
          </div>
        </>
      )}

      <h2 className="sub">Restart with content</h2>
      <p className="note">Reopen this built course — no rebuild, no token spend.</p>
      <div className="row">
        <button className="btn" onClick={() => restart("resume")}>Resume last session</button>
        <button className="btn secondary" onClick={() => restart("fresh")}>New session over same content</button>
      </div>
      {msg && <p className="note">{msg}</p>}

      <div style={{ marginTop: 32 }}>
        <AppFeedback pageKey="final_feedback" />
      </div>
    </div>
  );
}
