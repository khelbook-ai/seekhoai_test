import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import MarkdownView from "../components/MarkdownView.jsx";
import FeedbackWidget from "../components/FeedbackWidget.jsx";
import CodeWalkthrough from "../components/CodeWalkthrough.jsx";
import OrderSteps from "../components/interactions/OrderSteps.jsx";
import FillBlanks from "../components/interactions/FillBlanks.jsx";
import ArchDiagram from "../components/interactions/ArchDiagram.jsx";

const DL_LABEL = { 1: "Easy", 2: "Medium", 3: "Hard" };
const TICK = { correct: "✓", wrong: "✗", unanswered: "○", reviewed: "▣" };
const RICH = { order: OrderSteps, blanks: FillBlanks, dragdrop: ArchDiagram };

// Render a rich interaction body (order/blanks/dragdrop), live or read-only.
function RichBody({ it, value, onChange, decided, solution, readonly }) {
  const Comp = RICH[it.type];
  if (!Comp) return null;
  return <Comp payload={it.payload} value={value} onChange={onChange}
    decided={decided} solution={solution} readonly={readonly} />;
}
// wrap the component's inner value into the backend response shape
function wrapResponse(type, v, it) {
  if (type === "order") return { order: v && v.length ? v : (it.payload.items || []).map((i) => i.id) };
  if (type === "blanks") return { answers: v || {} };
  if (type === "dragdrop") return { mapping: v || {} };
  return {};
}
function richComplete(type, v, it) {
  if (type === "order") return true;
  if (type === "blanks") return Object.keys(v || {}).length >= (it.payload.blanks || []).length;
  if (type === "dragdrop") return Object.keys(v || {}).length >= (it.payload.boxes || []).length;
  return false;
}

// Learning screen (spec 07 §2). Session is RESUMED (progress + score survive navigation).
// A sub-tab rail lists every question per subtopic with a green/red/neutral tick; completed
// questions open read-only (no reattempt). Content+Hint sit at the top of each question.
export default function Learning() {
  const { courseId } = useParams();
  const nav = useNavigate();
  const [sid, setSid] = useState(null);
  const [map, setMap] = useState(null);
  const [it, setIt] = useState(null);          // current (answerable) interaction
  const [score, setScore] = useState(0);
  const [review, setReview] = useState(null);  // a completed interaction being viewed read-only
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  // per-question interactive state
  const [selected, setSelected] = useState(null);
  const [answerText, setAnswerText] = useState("");
  const [richResp, setRichResp] = useState(null);   // order/blanks/dragdrop response
  const [hints, setHints] = useState([]);
  const [hintsUsed, setHintsUsed] = useState(0);
  const [content, setContent] = useState(null);
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.openSession(courseId).then((s) => {
      setSid(s.session_id); setIt(s.interaction); setMap(s.map); setScore(s.running_score);
      setReview(null); resetLocal(); setLoading(false);
    }).catch((e) => { setErr(e.message); setLoading(false); });
  }, [courseId]);

  function resetLocal() {
    setSelected(null); setAnswerText(""); setRichResp(null); setHints([]); setHintsUsed(0);
    setContent(null); setResult(null);
  }
  async function refreshMap(s = sid) { try { setMap(await api.sessionMap(s)); } catch {} }

  async function goCurrent() {
    setReview(null); resetLocal();
    const d = await api.currentInteraction(sid);
    setIt(d.interaction);
  }
  async function openReview(id) {
    setLoading(true);
    try { setReview(await api.reviewInteraction(sid, id)); } catch (e) { setErr(e.message); }
    setLoading(false);
  }

  async function reveal() {
    const level = hintsUsed + 1;
    if (level > (it.hints_available || 3)) return;
    const h = await api.getHint(sid, it.id, level);
    setHints((p) => [...p, { level: h.level, text_md: h.text_md }]); setHintsUsed(h.hints_used);
  }
  async function showContent() {
    if (content) { setContent(null); return; }
    const c = await api.getContent(sid, it.id); setContent(c.content_md);
  }
  async function submit() {
    setSubmitting(true); setErr(null);
    try {
      const payload = it.type === "mcq" ? { interaction_id: it.id, selected_label: selected }
        : it.type === "qa" ? { interaction_id: it.id, answer_text: answerText }
        : { interaction_id: it.id, response: wrapResponse(it.type, richResp, it) };
      const r = await api.submitAnswer(sid, payload);
      setResult(r); setScore(r.running_score); refreshMap();
    } catch (e) { setErr(e.message); } finally { setSubmitting(false); }
  }
  function next() {
    resetLocal();
    if (result?.next) { setIt(result.next); setReview(null); }
    else { setIt(null); refreshMap(); }
  }
  async function walkthroughDone() {
    const r = await api.submitAnswer(sid, { interaction_id: it.id });  // mark reviewed (non-scored)
    setScore(r.running_score); refreshMap(); resetLocal();
    if (r.next) setIt(r.next); else { setIt(null); refreshMap(); }
  }

  if (err) return <div className="wrap"><p className="err">{err}</p>
    <button className="btn secondary" onClick={() => nav(`/course/${courseId}`)}>Back</button></div>;
  if (loading && !map) return <div className="wrap"><p className="spinner"><span className="spin" /> Loading your session…</p></div>;

  const prog = it?.progress || (map ? { answered: map.answered, total: map.total,
    pct: map.total ? Math.round((map.answered / map.total) * 100) : 0 } : null);

  return (
    <div className="learn">
      <Rail map={map} currentId={it?.id} reviewId={review?.id} score={score}
        onCurrent={goCurrent} onReview={openReview} />
      <div className="learn-main">
        {prog && (
          <div className="progress-wrap">
            <div className="progress-head">
              <span>{it?.progress?.current_topic ? `Topic: ${it.progress.current_topic}` : "Progress"}
                {it?.progress ? ` · ${it.progress.topic_count} topics` : ""}</span>
              <span className="mono">{prog.pct}% · {prog.answered}/{prog.total} done
                {it?.progress ? ` · Q ${it.progress.position}/${it.progress.total}` : ""}</span>
            </div>
            <div className="progress-bar"><div className="progress-fill" style={{ width: `${prog.pct}%` }} /></div>
          </div>
        )}

        {review ? <ReviewPanel r={review} onBack={goCurrent} />
          : it && it.type === "walkthrough"
            ? <><div className="header"><span>{it.subtopic}<span className="badge">code walkthrough</span></span></div>
                <CodeWalkthrough wt={it.walkthrough} onDone={walkthroughDone} doneLabel="I've reviewed this →" /></>
          : it ? <Question it={it} {...{ selected, setSelected, answerText, setAnswerText, richResp, setRichResp,
              hints, hintsUsed, content, result, submitting, reveal, showContent, submit, next }} />
          : <Complete score={score} onDash={() => nav(`/course/${courseId}/dashboard?session=${sid}`)}
              onOverview={() => nav(`/course/${courseId}`)} />}
      </div>
    </div>
  );
}

// --- sub-tab rail: subtopics with per-question ticks (spec 07 §2) -----------
function Rail({ map, currentId, reviewId, score, onCurrent, onReview }) {
  if (!map) return null;
  return (
    <aside className="rail">
      <div className="rail-score">Score <strong>{score}</strong></div>
      {map.groups.map((g) => (
        <div key={g.subtopic_id} className="rail-group">
          <div className="rail-sub">{g.subtopic}</div>
          {g.items.map((x, i) => {
            const done = x.status !== "unanswered";
            const clickable = done || x.is_current;
            const active = x.id === reviewId || (x.is_current && !reviewId);
            return (
              <button key={x.id} disabled={!clickable}
                className={`rail-item ${x.status} ${active ? "active" : ""}`}
                onClick={() => (x.is_current ? onCurrent() : onReview(x.id))}
                title={done ? "Review" : x.is_current ? "Current question" : "Not reached yet"}>
                <span className={`tick ${x.status}`}>{x.is_current && !done ? "▸" : TICK[x.status]}</span>
                <span>Q{i + 1} · {x.type.toUpperCase()} · DL{x.dl}</span>
              </button>
            );
          })}
        </div>
      ))}
    </aside>
  );
}

// --- read-only review of a completed question (no reattempt) ---------------
function ReviewPanel({ r, onBack }) {
  if (r.type === "walkthrough") {
    return (
      <div>
        <div className="header">
          <span>{r.subtopic}<span className="badge">code walkthrough</span></span>
          <button className="link" onClick={onBack}>← back to current</button>
        </div>
        <CodeWalkthrough wt={r.walkthrough} readonly />
      </div>
    );
  }
  if (RICH[r.type]) {
    const inner = r.type === "order" ? r.your_response?.order
      : r.type === "blanks" ? r.your_response?.answers : r.your_response?.mapping;
    return (
      <div>
        <div className="header">
          <span>{r.subtopic}<span className={"badge dl dl" + r.dl}>DL{r.dl}</span>
            <span className={"badge " + (r.is_correct ? "" : "flag")}>{r.is_correct ? "correct" : "incorrect"}</span></span>
          <button className="link" onClick={onBack}>← back to current</button>
        </div>
        <div className="question"><MarkdownView>{r.question_md}</MarkdownView></div>
        <RichBody it={{ type: r.type, payload: r.payload }} value={inner} onChange={() => {}}
          decided solution={r.payload} readonly />
        {r.content_md && <div className="panel box"><h3>Content</h3><MarkdownView>{r.content_md}</MarkdownView></div>}
      </div>
    );
  }
  return (
    <div>
      <div className="header">
        <span>{r.subtopic}<span className={"badge dl dl" + r.dl}>DL{r.dl}</span>
          <span className="badge">reviewing</span></span>
        <button className="link" onClick={onBack}>← back to current</button>
      </div>
      {r.diagram_ref && <div className="diagram"><img src={`/api/blobs/${r.diagram_ref}`} alt="diagram" /></div>}
      <div className="question"><MarkdownView>{r.question_md}</MarkdownView></div>

      {r.type === "mcq" ? (
        <div className="options">
          {r.options.map((o) => {
            let cls = "option";
            if (o.is_correct) cls += " correct";
            else if (o.label === r.your_answer) cls += " incorrect";
            return <div key={o.label} className={cls}>
              <span className="label">{o.label}</span><span><MarkdownView>{o.text}</MarkdownView></span>
              {o.label === r.your_answer && <span className="you">your answer</span>}
            </div>;
          })}
        </div>
      ) : (
        <div className="panel box"><h3>Your answer</h3><MarkdownView>{r.your_answer || "(no answer)"}</MarkdownView></div>
      )}

      <div className={"result " + (r.is_correct ? "correct" : "incorrect")}>
        {r.is_correct ? "You got this right" : "You missed this one"}
        <span className="detail">Scored {r.score_awarded} · {r.hints_used} hint(s) used</span>
      </div>
      {r.feedback_md && <div className="panel box"><h3>Feedback on your answer</h3><MarkdownView>{r.feedback_md}</MarkdownView></div>}
      {r.content_md && <div className="panel box"><h3>Content</h3><MarkdownView>{r.content_md}</MarkdownView></div>}
    </div>
  );
}

// --- the interactive question ----------------------------------------------
function Question({ it, selected, setSelected, answerText, setAnswerText, richResp, setRichResp,
                    hints, hintsUsed, content, result, submitting, reveal, showContent, submit, next }) {
  const decided = !!result;
  const isFollowup = !!it.escalated_from;
  const isRich = !!RICH[it.type];
  const hintsLeft = (it.hints_available || 3) - hintsUsed;
  const ladder = [...hints].sort((a, b) => b.level - a.level);
  const canSubmit = it.type === "mcq" ? !!selected
    : isRich ? richComplete(it.type, richResp, it)
    : answerText.trim().length > 3;

  return (
    <div>
      <div className="header">
        <span>{it.subtopic}
          <span className={"badge dl dl" + it.dl}>Difficulty: {DL_LABEL[it.dl] || `DL${it.dl}`} (DL{it.dl})</span>
          {isFollowup && <span className="badge">follow-up</span>}
        </span>
      </div>
      {isFollowup && !decided && (
        <p className="note followup-note">Let's find where this idea slipped — answer in a
          sentence or two. No equations needed.</p>
      )}
      {it.diagram_ref && <div className="diagram"><img src={`/api/blobs/${it.diagram_ref}`} alt="diagram" /></div>}
      <div className="question"><MarkdownView>{it.question_md}</MarkdownView></div>

      <div className="actions">
        <button className="action-btn" onClick={showContent}>{content ? "Hide content" : "Content"}</button>
        <button className="action-btn" onClick={reveal} disabled={hintsLeft <= 0 || decided}>
          {hintsLeft > 0 ? `Hint (${hintsUsed + 1} of ${it.hints_available || 3}, −1)` : "No hints left"}
        </button>
      </div>
      {content && <div className="panel box"><h3>Content</h3><MarkdownView>{content}</MarkdownView></div>}
      {ladder.length > 0 && (
        <div className="panel box hints-box">
          {ladder.map((h) => <div key={h.level} className="hint-rung"><h3>Hint {h.level}</h3>
            <MarkdownView>{h.text_md}</MarkdownView></div>)}
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
            return <button key={o.label} className={cls} disabled={decided}
              onClick={() => setSelected(o.label)}>
              <span className="label">{o.label}</span><span><MarkdownView>{o.text}</MarkdownView></span>
            </button>;
          })}
        </div>
      ) : isRich ? (
        <RichBody it={it} value={richResp} onChange={setRichResp} decided={decided}
          solution={result?.solution} />
      ) : (
        <textarea className="text" placeholder="Answer in a sentence or two…" value={answerText}
          disabled={decided} onChange={(e) => setAnswerText(e.target.value)} style={{ minHeight: 130 }} />
      )}

      {!decided && (
        <button className="submit" disabled={!canSubmit || submitting} onClick={submit}>
          {submitting ? <><span className="spin" /> Checking your answer…</> : "Submit answer"}
        </button>
      )}

      {decided && (
        <div className={"result " + (result.correct ? "correct" : "incorrect")}>
          {it.type === "mcq"
            ? (result.correct ? "Correct!" : `Not quite — the answer was ${result.correct_label}.`)
            : isRich
            ? (result.correct ? "Correct!" : "Not quite — the correct answer is shown above.")
            : `Graded: ${result.band}`}
          <span className="detail">+{result.score_awarded} points
            {result.escalated && " · here's a quick follow-up to pinpoint the gap"}</span>
          {it.type === "qa" && result.feedback_md && (
            <div className="panel" style={{ marginTop: 16 }}>
              <h3>Feedback on your answer</h3><MarkdownView>{result.feedback_md}</MarkdownView>
              {result.rubric_misses?.length > 0 && <p className="note">Missed: {result.rubric_misses.join("; ")}</p>}
            </div>
          )}
          <button className="btn" style={{ marginTop: 18 }} onClick={next}>
            {result.next ? "Next question" : "Finish course"}
          </button>
        </div>
      )}
      <FeedbackWidget interactionId={it.id} />
    </div>
  );
}

function Complete({ score, onDash, onOverview }) {
  return (
    <div>
      <h1 className="title">Course complete 🎉</h1>
      <p className="lead">Final score: <strong>{score}</strong>. You can still review any question
        from the list on the left.</p>
      <div className="row">
        <button className="btn" onClick={onDash}>See your dashboard</button>
        <button className="btn secondary" onClick={onOverview}>Course overview</button>
      </div>
    </div>
  );
}
