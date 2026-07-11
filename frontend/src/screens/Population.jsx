import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import BuildLog from "../components/BuildLog.jsx";

// Course population / curriculum view (spec 07 §5). Polls while building; shows derived
// counts, cost estimate vs actual + reason, and per-subtopic detail.
export default function Population() {
  const { courseId } = useParams();
  const nav = useNavigate();
  const [course, setCourse] = useState(null);
  const [pop, setPop] = useState(null);
  const [err, setErr] = useState(null);
  const timer = useRef(null);

  async function refresh() {
    try {
      const c = await api.getCourse(courseId);
      setCourse(c);
      if (["built", "building", "failed"].includes(c.status)) {
        setPop(await api.population(courseId));
      }
      if (c.status !== "building" && timer.current) { clearInterval(timer.current); timer.current = null; }
    } catch (e) { setErr(e.message); }
  }

  useEffect(() => {
    refresh();
    timer.current = setInterval(refresh, 6000);
    return () => timer.current && clearInterval(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseId]);

  if (err) return <div className="wrap"><p className="err">{err}</p></div>;
  if (!course) return <div className="wrap"><p className="spinner">Loading…</p></div>;

  const building = course.status === "building";
  const t = pop?.totals;
  const cost = pop?.cost;
  const prog = pop?.progress;

  return (
    <div className="wrap">
      <h1 className="title">{course.title}</h1>
      <p className="lead">
        Status: <strong>{course.status}</strong>
        {building && <span className="spinner"> · scouting the live web, generating, checking &amp; verifying…</span>}
      </p>

      {prog && (course.status === "building" || course.status === "built") && (
        <div className="progress-wrap">
          <div className="progress-head">
            <span>Build progress</span>
            <span className="mono">{prog.pct}% · {prog.built_subtopics}/{prog.total_subtopics} subtopics</span>
          </div>
          <div className="progress-bar"><div className="progress-fill" style={{ width: `${prog.pct}%` }} /></div>
        </div>
      )}

      <h2 className="sub">Build log <span className="note">(technical trace — tool use, MCP scraping, checks)</span></h2>
      <BuildLog courseId={courseId} active={building} />

      {t && (
        <>
          <div className="stat-row">
            <div className="stat"><div className="n">{t.mcqs}</div><div className="k">MCQs</div></div>
            <div className="stat"><div className="n">{t.qa}</div><div className="k">Q&amp;A</div></div>
            <div className="stat"><div className="n">{t.illustrations.total}</div>
              <div className="k">Illustrations</div>
              <div className="note">{t.illustrations.sourced} sourced · {t.illustrations.generated} generated</div></div>
            <div className="stat"><div className="n">{t.sources.total}</div><div className="k">Sources</div></div>
          </div>
          <p className="note">
            Sources by format: {Object.entries(t.sources.by_format).map(([k, v]) => `${v} ${k}`).join(", ") || "—"}
            {t.newest_source && ` · newest: ${t.newest_source}`}
            {t.flagged_for_review > 0 && <span className="badge flag">{t.flagged_for_review} flagged for review</span>}
          </p>

          <div className="card">
            <div className="cost-line"><span>Estimated</span>
              <span className="mono">${(cost.estimated ?? 0).toFixed(4)}</span></div>
            <div className="cost-line"><span>Actual</span>
              <span className="mono">{cost.actual != null ? `$${cost.actual.toFixed(4)}` : "—"}</span></div>
            {cost.actual != null && (
              <div className="cost-line"><span>Delta</span>
                <span className="mono">${cost.delta_abs?.toFixed(4)} ({cost.delta_pct}%)</span></div>
            )}
            {cost.reconciliation?.summary && <p className="note" style={{ marginTop: 8 }}>{cost.reconciliation.summary}</p>}
          </div>

          <h2 className="sub">Subtopics</h2>
          {pop.subtopics.map((s) => (
            <div className="card" key={s.subtopic_id}>
              <strong>{s.name}</strong> <span className="badge">DL{s.calibrated_dl}</span>
              {s.partially_sourced && <span className="badge warn">partially sourced</span>}
              <p className="note" style={{ marginTop: 4 }}>{s.description}</p>
              <p className="note">{s.mcqs} MCQs · {s.qa} Q&amp;A · {s.illustrations} illustrations
                {s.audit_score != null && ` · audit ${(s.audit_score * 100) | 0}%`}</p>
              {s.sources.length > 0 && (
                <div className="src">Sources: {s.sources.map((so, i) => (
                  <span key={i}><a href={so.url} target="_blank" rel="noreferrer">{so.title || so.url}</a>
                    {so.type ? ` (${so.type}${so.published ? `, ${so.published}` : ""})` : ""}{i < s.sources.length - 1 ? "; " : ""}</span>
                ))}</div>
              )}
            </div>
          ))}
        </>
      )}

      <div className="row" style={{ marginTop: 24 }}>
        <button className="btn" disabled={course.status !== "built"} onClick={() => nav(`/learn/${courseId}`)}>
          {course.status === "built" ? "Start learning" : "Building…"}
        </button>
        <button className="btn secondary" onClick={() => nav(`/course/${courseId}/dashboard`)}>Dashboard</button>
      </div>
      <p className="note" style={{ marginTop: 12 }}>Course id: <code>{courseId}</code></p>
    </div>
  );
}
