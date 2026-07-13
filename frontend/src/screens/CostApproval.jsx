import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import ThumbsFeedback from "../components/ThumbsFeedback.jsx";

// Format minutes as "~45 min" or "~1h 20m".
export function fmtMins(m) {
  if (!m) return "—";
  if (m < 60) return `~${m} min`;
  const h = Math.floor(m / 60), r = m % 60;
  return r ? `~${h}h ${r}m` : `~${h}h`;
}

// Cost-approval screen (spec 07 §4). No content is generated until Approve is pressed.
export default function CostApproval() {
  const { courseId } = useParams();
  const nav = useNavigate();
  const [course, setCourse] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => { api.getCourse(courseId).then(setCourse).catch((e) => setErr(e.message)); }, [courseId]);

  if (err) return <div className="wrap"><p className="err">{err}</p></div>;
  if (!course) return <div className="wrap"><p className="spinner">Loading…</p></div>;

  const est = course.cost_estimate || {};
  const cur = course.curriculum || {};
  const byPhase = est.by_phase || {};
  const topSubs = (est.by_subtopic || []).slice().sort((a, b) => b.estimate - a.estimate).slice(0, 5);

  async function approve(ok) {
    setBusy(true); setErr(null);
    try {
      const r = await api.costApproval(courseId, ok);
      if (r.status === "building") nav(`/course/${courseId}`);
      else nav("/");
    } catch (e) { setErr(e.message); setBusy(false); }
  }

  return (
    <div className="wrap">
      <h1 className="title">{cur.title || course.title}</h1>
      <p className="lead">Estimated build cost. Nothing is generated until you approve.</p>

      <div className="card">
        <div className="cost-line"><span>Estimated total</span>
          <strong className="mono">${(est.total_estimate ?? 0).toFixed(4)}</strong></div>
        {Object.entries(byPhase).map(([k, v]) => (
          <div className="cost-line" key={k}><span style={{ textTransform: "capitalize" }}>{k}</span>
            <span className="mono">${Number(v).toFixed(4)}</span></div>
        ))}
        {est.calibration && (
          <div className="cost-line"><span>Calibrated from history</span>
            <span className="mono">×{est.calibration.factor} · raw ${Number(est.raw_estimate).toFixed(4)}</span></div>
        )}
        <p className="note">Currency: USD · buffer {est.buffer_pct}% · ~{(est.tokens_estimate || 0).toLocaleString()} tokens ·
          currency mode: {course.currency_mode}</p>
        {est.est_completion_minutes > 0 && (
          <p className="note">⏱ Average time to finish the course: <strong>{fmtMins(est.est_completion_minutes)}</strong></p>
        )}
        {est.calibration && (
          <p className="note">Estimate tuned from {est.calibration.samples} similar past course(s) whose actual cost
            ran ×{est.calibration.factor} the raw heuristic — see their cost reconciliation .md files.</p>
        )}
      </div>

      <h2 className="sub">Curriculum</h2>
      {(cur.topics || []).map((t) => (
        <div className="card" key={t.name}>
          <strong>{t.name}</strong> <span className="badge">DL{t.calibrated_dl}</span>
          <p className="note" style={{ marginTop: 4 }}>{t.rationale}</p>
          <ul style={{ margin: "6px 0 0", paddingLeft: 20 }}>
            {t.subtopics.map((s) => (
              <li key={s.name}>{s.name} <span className="note">· {s.target_question_count} questions</span></li>
            ))}
          </ul>
        </div>
      ))}

      {topSubs.length > 0 && (
        <>
          <h2 className="sub">Top subtopics by cost</h2>
          {topSubs.map((s) => (
            <div className="cost-line" key={s.subtopic}><span>{s.subtopic}</span>
              <span className="mono">${Number(s.estimate).toFixed(4)}</span></div>
          ))}
        </>
      )}

      {(est.assumptions || []).length > 0 && (
        <p className="note" style={{ marginTop: 16 }}>Assumptions: {est.assumptions.join("; ")}</p>
      )}
      {err && <p className="err">{err}</p>}

      {/* One-way commit (spec 07 §0): approval buttons only while awaiting_cost. Once the
          build has started/finished this is read-only — start a new course to change scope. */}
      {course.status === "awaiting_cost" ? (
        <div className="row" style={{ marginTop: 24 }}>
          <button className="btn" disabled={busy} onClick={() => approve(true)}>
            {busy ? <><span className="spin" /> Starting build…</> : "Approve & build"}</button>
          <button className="btn secondary" disabled={busy} onClick={() => approve(false)}>Revise scope</button>
        </div>
      ) : (
        <div className="row" style={{ marginTop: 24 }}>
          <p className="note locked-note">Cost already approved — this course is
            {course.status === "built" ? " built" : " building"}. To change the scope or cost,
            start a <span className="link" onClick={() => nav("/")}>new course</span>.</p>
          <button className="btn" onClick={() => nav(`/course/${courseId}`)}>Go to build</button>
        </div>
      )}
      <div className="thumbs-bar">
        <ThumbsFeedback kind="page" id={`cost:${courseId}`} label="Is the estimated cost & curriculum reasonable?" />
      </div>
    </div>
  );
}
