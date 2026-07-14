import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import AppFeedback from "../components/AppFeedback.jsx";
import ThumbsFeedback from "../components/ThumbsFeedback.jsx";

// Landing capabilities (spec 07 §3): show what the product does before the learner commits.
const CAPS = [
  { ico: "✍️", t: "Start with a prompt", d: "Type what you want to learn and who you are. That's the whole setup — no syllabus hunting, no course catalog." },
  { ico: "🧭", t: "Calibrated to you", d: "A few quick choices tune the depth, framing and examples. A VP at a bank and a junior ML engineer asking the same thing get different courses." },
  { ico: "🌐", t: "Researched live, not canned", d: "It reads the current web — papers, docs and reputable sources — and builds the course from what's true today, figures included." },
  { ico: "🎯", t: "Learn by doing, not watching", d: "No videos. Every idea arrives as something you do — MCQs, ordering steps, filling blanks, guided code tours and short Q&A." },
  { ico: "🪜", t: "Never stuck, never bored", d: "Escalating hints, an on-demand content panel, and adaptive difficulty that follows how you're actually doing — get one wrong and it pinpoints the gap." },
  { ico: "📊", t: "See your progress", d: "Live score, difficulty and accuracy as you go, a weakness dashboard after, and a full record of everything you've learned." },
];

// Course-creation page (spec 07 §3). Two big guarded inputs. Blocked prompts show a
// clear inline reason and keep the input editable.
export default function CourseCreation() {
  const nav = useNavigate();
  const [prompt, setPrompt] = useState("");
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [restartId, setRestartId] = useState("");

  function route(r) {
    if (r.status === "refused") {
      setErr(`Out of scope: ${r.reason}${r.suggested_reframing ? ` — try: ${r.suggested_reframing}` : ""}`);
    } else if (r.status === "awaiting_clarification") {
      nav(`/course/${r.course_id}/clarify`, { state: { questions: r.questions } });
    } else if (r.status === "awaiting_cost") {
      nav(`/course/${r.course_id}/cost`);
    } else {
      nav(`/course/${r.course_id}`);
    }
  }

  async function create() {
    setErr(null); setBusy(true);
    try { route(await api.createCourse(prompt, role)); }
    catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }

  async function uploadFile(e) {
    const f = e.target.files && e.target.files[0];
    e.target.value = "";               // allow re-selecting the same file
    if (!f) return;
    setErr(null); setBusy(true);
    try { route(await api.createCourseFromFile(f, role)); }
    catch (e2) { setErr(e2.message); }
    finally { setBusy(false); }
  }

  return (
    <div className="wrap hero">
      <h1 className="title">Learn anything in AI — by doing, not watching.</h1>
      <p className="tagline">Tell Seekhai a topic and your role. It researches the live web and
        builds you a full course, calibrated to the choices you make — then teaches it entirely
        through interactions. No lectures. No videos. Just you, actively working through ideas,
        with hints and explanations exactly when you need them.</p>
      <p className="lead">Thanks to rich, hands-on interactions — MCQs, ordering steps, code
        walkthroughs, quick Q&amp;A — learners stay engaged and remember more, without a single
        talking-head video.</p>

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

      <div className="upload-row">
        <span className="upload-or">or</span>
        <label className={"btn secondary" + (busy ? " disabled" : "")}>
          📎 Build from a PDF or slide deck
          <input type="file" accept=".pdf,.pptx,.docx,.txt,.md" hidden disabled={busy} onChange={uploadFile} />
        </label>
        <span className="note">We read your file and build the course from it — PDF, slides, or docs.</span>
      </div>

      <div className="caps">
        {CAPS.map((c) => (
          <div key={c.t} className="cap">
            <div className="cap-ico">{c.ico}</div>
            <h3>{c.t}</h3>
            <p>{c.d}</p>
          </div>
        ))}
      </div>
      <div className="pill-row">
        <span className="pill">Adaptive difficulty</span>
        <span className="pill">Live-web research</span>
        <span className="pill">Escalating hints</span>
        <span className="pill">Code walkthroughs</span>
        <span className="pill">Weakness tracking</span>
        <span className="pill">Build from PDF / slides</span>
        <span className="pill">No videos needed</span>
      </div>

      <h2 className="sub">Already built a course?</h2>
      <p className="note">Restart with existing content — no rebuild, no token spend.</p>
      <div className="row">
        <input className="text" style={{ flex: 1 }} placeholder="paste a course id"
          value={restartId} onChange={(e) => setRestartId(e.target.value)} />
        <button className="btn secondary" disabled={!restartId.trim()}
          onClick={() => nav(`/course/${restartId.trim()}`)}>Open</button>
      </div>

      <div className="thumbs-bar">
        <ThumbsFeedback kind="page" id="course_creation" label="Does this page explain what Seekhai does?" />
      </div>
      <div style={{ marginTop: 20 }}>
        <AppFeedback pageKey="course_creation" />
      </div>
    </div>
  );
}
