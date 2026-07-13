import React, { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import ThumbsFeedback from "../components/ThumbsFeedback.jsx";

// Clarification questions as tappable option chips (spec 07 §3). ≤10, often fewer.
// A question may be multi-select (spec 01 §3) — e.g. "which areas of RL matter to you?" —
// in which case several chips can be toggled and the answer is the joined selection.
// Questions come from router state on the first pass, else load from the API so the tester
// can navigate back to them from the sidebar at any time.
export default function Clarification() {
  const { courseId } = useParams();
  const nav = useNavigate();
  const stateQs = useLocation().state?.questions;
  const [questions, setQuestions] = useState(stateQs || []);
  const [answers, setAnswers] = useState({});      // ordinal -> string[] (selected options)
  const [input, setInput] = useState(null);        // the learner's own prompt + role (item 5)
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  // This stage is a one-way commit (spec 07 §0): editable only before the curriculum is
  // designed. Once past clarification it's read-only — start a new course to change anything.
  const locked = status != null && !["intake", "awaiting_clarification"].includes(status);

  // Always load the course so we can show the learner's original input, even on the first pass.
  useEffect(() => {
    api.getCourse(courseId).then((c) => {
      setStatus(c.status);
      setInput({ prompt: c.raw_prompt, role: c.raw_role, currency: c.currency_mode });
      if (!(stateQs && stateQs.length)) {
        const qs = c.clarifications || [];
        setQuestions(qs);
        const pre = {};
        qs.forEach((q) => { if (q.answer) pre[q.ordinal] = q.answer.split(" · ").filter(Boolean); });
        setAnswers(pre);
      }
    }).catch((e) => setErr(e.message));
  }, [courseId, stateQs]);

  function toggle(q, opt) {
    setAnswers((a) => {
      const cur = a[q.ordinal] || [];
      if (q.multi_select) {
        return { ...a, [q.ordinal]: cur.includes(opt) ? cur.filter((x) => x !== opt) : [...cur, opt] };
      }
      return { ...a, [q.ordinal]: [opt] };   // single-select replaces
    });
  }

  async function submit() {
    setErr(null); setBusy(true);
    try {
      // Backend takes one string per question; join a multi-select into a readable list.
      const payload = {};
      Object.entries(answers).forEach(([ord, sel]) => { payload[ord] = (sel || []).join(" · "); });
      const r = await api.clarify(courseId, payload);
      if (r.status === "refused") setErr(`Out of scope: ${r.reason}`);
      else nav(`/course/${courseId}/cost`);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  }

  const allAnswered = questions.length > 0 && questions.every((q) => (answers[q.ordinal] || []).length > 0);

  return (
    <div className="wrap">
      <h1 className="title">Student Input</h1>
      <p className="lead">What you asked for, and a few questions that tune the difficulty,
        depth, and framing of your course.</p>

      {input && (input.prompt || input.role) && (
        <div className="card">
          <div className="io-row"><span className="io-k">You want to learn</span>
            <span className="io-v">{input.prompt || "—"}</span></div>
          <div className="io-row"><span className="io-k">Your role</span>
            <span className="io-v">{input.role || "—"}</span></div>
          {input.currency && <div className="io-row"><span className="io-k">Mode</span>
            <span className="io-v">{input.currency === "latest_research" ? "Latest research" : "Fundamentals"}</span></div>}
        </div>
      )}

      {questions.length > 0 && <h2 className="sub">A few quick questions</h2>}
      {questions.map((q) => (
        <div key={q.ordinal} className="q-block">
          <div className="qtext">
            {q.q}
            {q.multi_select && <span className="badge">choose any that apply</span>}
          </div>
          <div className="chips">
            {q.options.map((opt) => (
              <button key={opt} disabled={locked}
                className={"chip" + ((answers[q.ordinal] || []).includes(opt) ? " selected" : "")}
                onClick={() => !locked && toggle(q, opt)}>
                {opt}
              </button>
            ))}
          </div>
        </div>
      ))}
      {err && <p className="err">{err}</p>}
      {locked ? (
        <p className="note locked-note">This course is already past setup — your input is locked.
          To change the topic, role, or answers, start a <a className="link" onClick={() => nav("/")}>new course</a>.</p>
      ) : (
        <button className="btn" disabled={busy || !allAnswered} onClick={submit}>
          {busy ? <><span className="spin" /> Designing your curriculum…</> : "Continue"}
        </button>
      )}
      {questions.length > 0 && (
        <div className="thumbs-bar">
          <ThumbsFeedback kind="page" id={`clarify:${courseId}`} label="Were these questions relevant?" />
        </div>
      )}
    </div>
  );
}
