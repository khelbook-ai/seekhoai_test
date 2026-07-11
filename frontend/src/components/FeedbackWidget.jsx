import React, { useRef, useState } from "react";
import { api } from "../api.js";

// Content feedback on a specific interaction, with image upload + text-linking (spec 06 §2/07).
// Select a span of your written feedback, then attach an image — the linked text becomes
// the image caption and is embedded inline in the persisted .md.
export default function FeedbackWidget({ interactionId }) {
  const [text, setText] = useState("");
  const [caption, setCaption] = useState("");
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [saved, setSaved] = useState(null);
  const [err, setErr] = useState(null);
  const taRef = useRef(null);

  function captureSelection() {
    const el = taRef.current;
    if (!el) return;
    const sel = text.substring(el.selectionStart, el.selectionEnd).trim();
    if (sel) setCaption(sel);
  }
  function attach(f) {
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
  }

  async function submit() {
    setErr(null);
    try {
      if (file) {
        const r = await api.contentFeedbackImage(interactionId, text, caption, file);
        setSaved(r.md_file_path);
      } else {
        const r = await api.contentFeedback(interactionId, text);
        setSaved(r.md_file_path);
      }
      setText(""); setCaption(""); setFile(null); setPreview(null);
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <details className="feedback">
      <summary>▸ Leave content feedback on this question</summary>
      <textarea
        ref={taRef}
        className="text"
        placeholder="What's good or wrong about this question's content?"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onMouseUp={captureSelection}
        onKeyUp={captureSelection}
        onPaste={(e) => {
          const item = [...e.clipboardData.items].find((i) => i.type.startsWith("image/"));
          if (item) attach(item.getAsFile());
        }}
        onDrop={(e) => { e.preventDefault(); attach(e.dataTransfer.files[0]); }}
      />
      <div className="row" style={{ marginTop: 10 }}>
        <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => attach(e.target.files[0])} />
        {file && (
          <span className="note">
            linked to: “{caption || "(select text to link)"}”
          </span>
        )}
      </div>
      {preview && <img className="fb-img" src={preview} alt="attachment preview" />}
      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn secondary" disabled={!text.trim()} onClick={submit}>Save feedback</button>
        {saved && <span className="note">Saved → {saved.split("/").slice(-2).join("/")}</span>}
        {err && <span className="err">{err}</span>}
      </div>
    </details>
  );
}
