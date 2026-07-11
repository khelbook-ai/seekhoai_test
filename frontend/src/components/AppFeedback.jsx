import React, { useState } from "react";
import { api } from "../api.js";

// Page-scoped application feedback (spec 06 §2 / 07). "How this page works / should work."
export default function AppFeedback({ pageKey }) {
  const [text, setText] = useState("");
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState(null);
  async function submit() {
    setErr(null);
    try { await api.appFeedback(pageKey, text); setSaved(true); setText(""); }
    catch (e) { setErr(e.message); }
  }
  return (
    <details className="feedback">
      <summary>▸ Application feedback on this page</summary>
      <textarea className="text" placeholder="How does this page work? What should change?"
        value={text} onChange={(e) => setText(e.target.value)} />
      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn secondary" disabled={!text.trim()} onClick={submit}>Send</button>
        {saved && <span className="note">Thanks — recorded.</span>}
        {err && <span className="err">{err}</span>}
      </div>
    </details>
  );
}
