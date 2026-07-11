import React, { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";

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
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (stateQs && stateQs.length) return;
    api.getCourse(courseId).then((c) => {
      const qs = c.clarifications || [];
      setQuestions(qs);
      const pre = {};
      qs.forEach((q) => { if (q.answer) pre[q.ordinal] = q.answer.split(" · ").filter(Boolean); });
      setAnswers(pre);
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
      <h1 className="title">A few quick questions</h1>
      <p className="lead">These tune the difficulty, depth, and framing of your course.</p>
      {questions.map((q) => (
        <div key={q.ordinal} className="q-block">
          <div className="qtext">
            {q.q}
            {q.multi_select && <span className="badge">choose any that apply</span>}
          </div>
          <div className="chips">
            {q.options.map((opt) => (
              <button key={opt}
                className={"chip" + ((answers[q.ordinal] || []).includes(opt) ? " selected" : "")}
                onClick={() => toggle(q, opt)}>
                {opt}
              </button>
            ))}
          </div>
        </div>
      ))}
      {err && <p className="err">{err}</p>}
      <button className="btn" disabled={busy || !allAnswered} onClick={submit}>
        {busy ? "Designing your curriculum…" : "Continue"}
      </button>
    </div>
  );
}
