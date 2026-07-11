import React, { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";

// Clarification questions as tappable option chips (spec 07 §3). ≤10, often fewer.
// Questions come from router state on the first pass, else load from the API so the
// tester can navigate back to them from the sidebar at any time.
export default function Clarification() {
  const { courseId } = useParams();
  const nav = useNavigate();
  const stateQs = useLocation().state?.questions;
  const [questions, setQuestions] = useState(stateQs || []);
  const [answers, setAnswers] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (stateQs && stateQs.length) return;
    api.getCourse(courseId).then((c) => {
      const qs = c.clarifications || [];
      setQuestions(qs);
      const pre = {};
      qs.forEach((q) => { if (q.answer) pre[q.ordinal] = q.answer; });
      setAnswers(pre);
    }).catch((e) => setErr(e.message));
  }, [courseId, stateQs]);

  async function submit() {
    setErr(null); setBusy(true);
    try {
      const r = await api.clarify(courseId, answers);
      if (r.status === "refused") setErr(`Out of scope: ${r.reason}`);
      else nav(`/course/${courseId}/cost`);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  }

  const allAnswered = questions.length > 0 && questions.every((q) => answers[q.ordinal]);

  return (
    <div className="wrap">
      <h1 className="title">A few quick questions</h1>
      <p className="lead">These tune the difficulty, depth, and framing of your course.</p>
      {questions.map((q) => (
        <div key={q.ordinal} className="q-block">
          <div className="qtext">{q.q}</div>
          <div className="chips">
            {q.options.map((opt) => (
              <button key={opt}
                className={"chip" + (answers[q.ordinal] === opt ? " selected" : "")}
                onClick={() => setAnswers((a) => ({ ...a, [q.ordinal]: opt }))}>
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
