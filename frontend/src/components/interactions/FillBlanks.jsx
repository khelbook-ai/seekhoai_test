import React, { useState } from "react";

// Fill-in-the-blanks interaction (spec 04 §1). Click a bank word to drop it into the selected
// (or next empty) blank; click a filled blank to clear it. `value` is { blank_id: word }.
// Graded all-or-nothing like an MCQ; `solution.blanks` reveals the correct words when decided.
export default function FillBlanks({ payload, value, onChange, decided, solution, readonly }) {
  const answers = value || {};
  const blankIds = (payload.blanks || []).map((b) => b.id);
  const [sel, setSel] = useState(blankIds[0]);
  const correctById = Object.fromEntries((solution?.blanks || []).map((b) => [b.id, b.answer]));
  const norm = (s) => (s || "").trim().toLowerCase();

  function placeWord(w) {
    if (decided || readonly) return;
    const target = sel && !answers[sel] ? sel : (blankIds.find((id) => !answers[id]) || sel);
    onChange({ ...answers, [target]: w });
  }
  function clearBlank(id) {
    if (decided || readonly) return;
    const next = { ...answers }; delete next[id]; onChange(next); setSel(id);
  }

  const usedCounts = {};
  Object.values(answers).forEach((w) => (usedCounts[w] = (usedCounts[w] || 0) + 1));

  return (
    <div className="blanks">
      <p className="blanks-text">
        {(payload.segments || []).map((seg, i) => {
          if (typeof seg === "string") return <span key={i}>{seg}</span>;
          const id = seg.blank;
          const val = answers[id];
          let cls = "blank-slot";
          if (decided) cls += norm(val) === norm(correctById[id]) ? " ok" : " bad";
          else if (id === sel) cls += " sel";
          return (
            <button key={i} className={cls} onClick={() => (val ? clearBlank(id) : setSel(id))}>
              {val || "     "}
              {decided && norm(val) !== norm(correctById[id]) && (
                <em className="blank-fix"> {correctById[id]}</em>
              )}
            </button>
          );
        })}
      </p>
      {!decided && !readonly && (
        <div className="bank">
          {(payload.bank || []).map((w, i) => (
            <button key={i} className="bank-word" onClick={() => placeWord(w)}>{w}</button>
          ))}
        </div>
      )}
    </div>
  );
}
