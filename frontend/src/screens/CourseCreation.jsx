import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import AppFeedback from "../components/AppFeedback.jsx";

// Course-creation page (spec 07 §3). Two big guarded inputs. Blocked prompts show a
// clear inline reason and keep the input editable.
export default function CourseCreation() {
  const nav = useNavigate();
  const [prompt, setPrompt] = useState("");
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [restartId, setRestartId] = useState("");

  async function create() {
    setErr(null); setBusy(true);
    try {
      const r = await api.createCourse(prompt, role);
      if (r.status === "refused") {
        setErr(`Out of scope: ${r.reason}${r.suggested_reframing ? ` — try: ${r.suggested_reframing}` : ""}`);
      } else if (r.status === "awaiting_clarification") {
        nav(`/course/${r.course_id}/clarify`, { state: { questions: r.questions } });
      } else if (r.status === "awaiting_cost") {
        nav(`/course/${r.course_id}/cost`);
      } else {
        nav(`/course/${r.course_id}`);
      }
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="wrap">
      <h1 className="title">Seekhai</h1>
      <p className="lead">Tell us a topic and your role. We research it on the live web and build
        a calibrated course you learn by doing.</p>

      <label className="field" htmlFor="p">What do you want to learn?</label>
      <input id="p" className="text" value={prompt} placeholder="e.g. the fundamentals of the Model Context Protocol"
        onChange={(e) => setPrompt(e.target.value)} />

      <label className="field" htmlFor="r">What's your role?</label>
      <input id="r" className="text" value={role} placeholder="e.g. backend engineer, VP at a bank, CS student"
        onChange={(e) => setRole(e.target.value)} />

      {err && <p className="err" style={{ marginTop: 16 }}>{err}</p>}

      <div className="row" style={{ marginTop: 22 }}>
        <button className="btn" disabled={busy || !prompt.trim()} onClick={create}>
          {busy ? <><span className="spin" /> Researching &amp; designing…</> : "Build my course"}
        </button>
      </div>

      <h2 className="sub">Already built a course?</h2>
      <p className="note">Restart with existing content — no rebuild, no token spend.</p>
      <div className="row">
        <input className="text" style={{ flex: 1 }} placeholder="paste a course id"
          value={restartId} onChange={(e) => setRestartId(e.target.value)} />
        <button className="btn secondary" disabled={!restartId.trim()}
          onClick={() => nav(`/course/${restartId.trim()}`)}>Open</button>
      </div>

      <div style={{ marginTop: 32 }}>
        <AppFeedback pageKey="course_creation" />
      </div>
    </div>
  );
}
