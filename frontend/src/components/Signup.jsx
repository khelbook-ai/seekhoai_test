import React, { useState } from "react";
import { api, setCurrentUser } from "../api.js";

// Simple name-only signup (spec 01 §5). The name ties this learner's courses, answers and
// weaknesses together so the Personalization agent can tune future courses to them.
export default function Signup({ onDone }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  async function go() {
    if (!name.trim()) return;
    setBusy(true); setErr(null);
    try {
      const u = await api.signup(name.trim());
      setCurrentUser(u);
      onDone(u);
    } catch (e) { setErr(e.message); setBusy(false); }
  }

  return (
    <div className="wrap" style={{ maxWidth: 460 }}>
      <h1 className="title">Welcome to Seekhai</h1>
      <p className="lead">What should we call you? Your name lets us learn how you learn and
        tune future courses to you.</p>
      <label className="field" htmlFor="n">Your name</label>
      <input id="n" className="text" value={name} autoFocus placeholder="e.g. Priya"
        onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && go()} />
      {err && <p className="err" style={{ marginTop: 12 }}>{err}</p>}
      <div className="row" style={{ marginTop: 20 }}>
        <button className="btn" disabled={busy || !name.trim()} onClick={go}>
          {busy ? <span className="spin" /> : "Start learning"}
        </button>
      </div>
    </div>
  );
}
