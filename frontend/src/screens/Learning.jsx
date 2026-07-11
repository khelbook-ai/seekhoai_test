import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import MarkdownView from "../components/MarkdownView.jsx";
import FeedbackWidget from "../components/FeedbackWidget.jsx";

// Difficulty labels shown on every question (spec 07 §2 requirement).
const DL_LABEL = { 1: "Easy", 2: "Medium", 3: "Hard" };

// Learning / interaction screen (spec 07 §2). Content + Hint sit in a fixed action row
// right below the question (at the top of the interaction); tapping either opens a box.
// A wrong MCQ escalates into a follow-up Q&A; the grader feedback is shown before advancing.
export default function Learning() {
  const { courseId } = useParams();
  const nav = useNavigate();
  const [sid, setSid] = useState(null);
  const [it, setIt] = useState(null);
  const [score, setScore] = useState(0);
  const [selected, setSelected] = useState(null);
  const [answerText, setAnswerText] = useState("");
  const [hints, setHints] = useState([]);       // all revealed hints (spec 04 §2 ladder)
  const [hintsUsed, setHintsUsed] = useState(0);
  const [content, setContent] = useState(null);
  const [result, setResult] = useState(null);
  const [complete, setComplete] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api.createSession(courseId).then((s) => { setSid(s.session_id); setIt(s.interaction); })
      .catch((e) => setErr(e.message));
  }, [courseId]);

  function resetForNext(next) {
    setSelected(null); setAnswerText(""); setHints([]); setHintsUsed(0);
    setContent(null); setResult(null);
    if (next) setIt(next); else setComplete(true);
  }

  async function reveal() {
    const level = hintsUsed + 1;
    if (level > (it.hints_available || 3)) return;
    const h = await api.getHint(sid, it.id, level);
    setHints((prev) => [...prev, { level: h.level, text_md: h.text_md }]);
    setHintsUsed(h.hints_used);
  }
  async function showContent() {
    if (content) { setContent(null); return; }
    const c = await api.getContent(sid, it.id);
    setContent(c.content_md);
  }
  async function submit() {
    setErr(null);
    try {
      const payload = it.type === "mcq"
        ? { interaction_id: it.id, selected_label: selected }
        : { interaction_id: it.id, answer_text: answerText };
      const r = await api.submitAnswer(sid, payload);
      setResult(r); setScore(r.running_score);
    } catch (e) { setErr(e.message); }
  }

  if (err) return <div className="wrap"><p className="err">{err}</p>
    <button className="btn secondary" onClick={() => nav(`/course/${courseId}`)}>Back</button></div>;
  if (!it && !complete) return <div className="wrap"><p className="spinner">Loading session…</p></div>;

  if (complete) {
    return (
      <div className="wrap">
        <h1 className="title">Course complete 🎉</h1>
        <p className="lead">Final score: <strong>{score}</strong></p>
        <div className="row">
          <button className="btn" onClick={() => nav(`/course/${courseId}/dashboard?session=${sid}`)}>See your dashboard</button>
          <button className="btn secondary" onClick={() => nav(`/course/${courseId}`)}>Course overview</button>
        </div>
      </div>
    );
  }

  const canSubmit = it.type === "mcq" ? !!selected : answerText.trim().length > 3;
  const decided = !!result;
  const isFollowup = !!it.escalated_from;
  const hintsLeft = (it.hints_available || 3) - hintsUsed;
  // Ladder display: newest hint first, earlier hints kept below it (spec 04 §2).
  const ladder = [...hints].sort((a, b) => b.level - a.level);

  return (
    <div className="wrap">
      <div className="header">
        <span>
          {it.subtopic}
          <span className={"badge dl dl" + it.dl}>Difficulty: {DL_LABEL[it.dl] || `DL${it.dl}`} (DL{it.dl})</span>
          {isFollowup && <span className="badge">follow-up</span>}
        </span>
        <span className="score">Score: {score}</span>
      </div>

      {isFollowup && !decided && (
        <p className="note followup-note">Let's find where this idea slipped — answer in a
          sentence or two. No equations needed.</p>
      )}

      {it.diagram_ref && (
        <div className="diagram"><img src={`/api/blobs/${it.diagram_ref}`} alt="question diagram" /></div>
      )}

      <div className="question"><MarkdownView>{it.question_md}</MarkdownView></div>

      {/* Fixed Content + Hint action row — at the top of the interaction, right under the
          question. Tapping either opens a box (spec 07 §2). */}
      <div className="actions">
        <button className="action-btn" onClick={showContent}>{content ? "Hide content" : "Content"}</button>
        <button className="action-btn" onClick={reveal} disabled={hintsLeft <= 0 || decided}>
          {hintsLeft > 0 ? `Hint (${hintsUsed + 1} of ${it.hints_available || 3}, −1)` : "No hints left"}
        </button>
      </div>

      {content && <div className="panel box"><h3>Content</h3><MarkdownView>{content}</MarkdownView></div>}
      {ladder.length > 0 && (
        <div className="panel box hints-box">
          {ladder.map((h) => (
            <div key={h.level} className="hint-rung">
              <h3>Hint {h.level}</h3>
              <MarkdownView>{h.text_md}</MarkdownView>
            </div>
          ))}
        </div>
      )}

      {it.type === "mcq" ? (
        <div className="options">
          {it.options.map((o) => {
            let cls = "option";
            if (decided) {
              if (o.label === result.correct_label) cls += " correct";
              else if (o.label === selected) cls += " incorrect";
            } else if (o.label === selected) cls += " selected";
            return (
              <button key={o.label} className={cls} disabled={decided}
                onClick={() => setSelected(o.label)}>
                <span className="label">{o.label}</span><span><MarkdownView>{o.text}</MarkdownView></span>
              </button>
            );
          })}
        </div>
      ) : (
        <textarea className="text" placeholder="Answer in a sentence or two…" value={answerText}
          disabled={decided} onChange={(e) => setAnswerText(e.target.value)} style={{ minHeight: 130 }} />
      )}

      {!decided && (
        <button className="submit" disabled={!canSubmit} onClick={submit}>Submit answer</button>
      )}

      {decided && (
        <div className={"result " + (result.correct ? "correct" : "incorrect")}>
          {it.type === "mcq"
            ? (result.correct ? "Correct!" : `Not quite — the answer was ${result.correct_label}.`)
            : `Graded: ${result.band}`}
          <span className="detail">+{result.score_awarded} points
            {result.escalated && " · here's a quick follow-up to pinpoint the gap"}</span>
          {it.type === "qa" && result.feedback_md && (
            <div className="panel" style={{ marginTop: 16 }}>
              <h3>Feedback on your answer</h3>
              <MarkdownView>{result.feedback_md}</MarkdownView>
              {result.rubric_misses?.length > 0 && (
                <p className="note">Missed: {result.rubric_misses.join("; ")}</p>
              )}
            </div>
          )}
          <button className="btn" style={{ marginTop: 18 }} onClick={() => resetForNext(result.next)}>
            {result.next ? "Next question" : "Finish course"}
          </button>
        </div>
      )}

      <FeedbackWidget interactionId={it.id} />
    </div>
  );
}
