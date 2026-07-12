import React, { useMemo, useRef, useState, useEffect } from "react";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import "prismjs/components/prism-clike";
import "prismjs/components/prism-javascript";
import "prismjs/components/prism-json";
import "prismjs/components/prism-bash";
import "prismjs/themes/prism.css";
import MarkdownView from "./MarkdownView.jsx";

const LINE_H = 22; // must match .wt-code line-height in styles.css

function grammarFor(lang) {
  const l = (lang || "").toLowerCase();
  if (l.includes("py")) return { g: Prism.languages.python, n: "python" };
  if (l.includes("js") || l.includes("ts")) return { g: Prism.languages.javascript, n: "javascript" };
  if (l.includes("json")) return { g: Prism.languages.json, n: "json" };
  if (l.includes("sh") || l.includes("bash")) return { g: Prism.languages.bash, n: "bash" };
  return { g: Prism.languages.clike, n: "clike" };
}

const fileIcon = (name) => (name.endsWith(".md") ? "📄" : name.endsWith(".toml") ? "⚙" :
  name.startsWith(".") ? "•" : "🐍");

// Guided read-only code walkthrough (spec 07 §2): file tree + syntax-highlighted viewer;
// each concept step highlights the relevant line ranges and switches files, like the reference
// widget. It is not scored — a paired MCQ (next question) tests it.
export default function CodeWalkthrough({ wt, onDone, doneLabel = "Continue →", readonly = false }) {
  const files = wt?.files || [];
  const steps = wt?.steps || [];
  const [step, setStep] = useState(0);
  const cur = steps[step] || {};
  const activeFile = cur.file || files[0]?.name;
  const file = files.find((f) => f.name === activeFile) || files[0];
  const codeRef = useRef(null);

  const html = useMemo(() => {
    if (!file) return "";
    const { g, n } = grammarFor(file.language);
    try { return Prism.highlight(file.content, g, n); } catch { return file.content; }
  }, [file]);

  const lines = (file?.content || "").split("\n");
  const ranges = cur.highlight || [];

  // scroll the first highlighted line into view when the step changes
  useEffect(() => {
    if (codeRef.current && ranges.length) {
      const top = (ranges[0][0] - 1) * LINE_H;
      codeRef.current.scrollTo({ top: Math.max(0, top - 40), behavior: "smooth" });
    }
  }, [step, activeFile]); // eslint-disable-line

  if (!file) return null;

  return (
    <div className="wt">
      {/* left: concept steps */}
      <div className="wt-steps">
        <div className="wt-col-head">Steps</div>
        {steps.map((s, i) => (
          <button key={i} className={"wt-step" + (i === step ? " active" : "")} onClick={() => setStep(i)}>
            <div className="wt-step-title">{s.title}</div>
            {i === step && <div className="wt-step-body"><MarkdownView>{s.concept_md}</MarkdownView></div>}
          </button>
        ))}
        <div className="wt-nav">
          <button className="btn secondary" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>← Previous</button>
          {step < steps.length - 1
            ? <button className="btn" onClick={() => setStep((s) => s + 1)}>Next →</button>
            : !readonly && <button className="btn" onClick={onDone}>{doneLabel}</button>}
        </div>
      </div>

      {/* right: file tree + code */}
      <div className="wt-code-pane">
        <div className="wt-files">
          <div className="wt-files-h">Files</div>
          {files.map((f) => (
            <button key={f.name} className={"wt-file" + (f.name === activeFile ? " active" : "")}
              onClick={() => {
                const s = steps.findIndex((x) => x.file === f.name);
                if (s >= 0) setStep(s);
              }} title={f.name}>
              <span>{fileIcon(f.name)}</span> {f.name}
            </button>
          ))}
        </div>
        <div className="wt-code-col">
          <div className="wt-filetab">{fileIcon(activeFile)} {activeFile}</div>
          <div className="wt-viewer" ref={codeRef}>
            <div className="wt-gutter">{lines.map((_, i) => <div key={i}>{i + 1}</div>)}</div>
            <div className="wt-codewrap" style={{ height: lines.length * LINE_H }}>
              {ranges.map((r, i) => (
                <div key={i} className="wt-band"
                  style={{ top: (r[0] - 1) * LINE_H, height: (r[1] - r[0] + 1) * LINE_H }} />
              ))}
              <pre className="wt-code"><code className={`language-${grammarFor(file.language).n}`}
                dangerouslySetInnerHTML={{ __html: html }} /></pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
