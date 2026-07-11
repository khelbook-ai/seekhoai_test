import React from "react";
import MarkdownView from "../MarkdownView.jsx";

// Order-the-steps interaction (spec 04 §1). Reorder with ↑/↓; graded all-or-nothing like an
// MCQ. `value` is the current ordered list of item ids. When `decided`, each row is marked
// against `solution.correct_order`.
export default function OrderSteps({ payload, value, onChange, decided, solution, readonly }) {
  const items = payload.items || [];
  const order = value && value.length ? value : items.map((i) => i.id);
  const byId = Object.fromEntries(items.map((i) => [i.id, i]));
  const correct = solution?.correct_order;

  function move(idx, dir) {
    const j = idx + dir;
    if (j < 0 || j >= order.length) return;
    const next = [...order];
    [next[idx], next[j]] = [next[j], next[idx]];
    onChange(next);
  }

  const shown = decided && correct ? correct : order;
  return (
    <div className="order-list">
      {shown.map((id, idx) => {
        let cls = "order-item";
        if (decided && correct) cls += order[idx] === correct[idx] ? " ok" : " bad";
        return (
          <div key={id} className={cls}>
            <span className="order-n">{idx + 1}</span>
            <span className="order-text"><MarkdownView>{byId[id]?.text || ""}</MarkdownView></span>
            {!decided && !readonly && (
              <span className="order-btns">
                <button className="link" disabled={idx === 0} onClick={() => move(idx, -1)}>↑</button>
                <button className="link" disabled={idx === order.length - 1} onClick={() => move(idx, 1)}>↓</button>
              </span>
            )}
          </div>
        );
      })}
      {decided && correct && <p className="note">Shown in the correct order; your wrong positions were marked.</p>}
    </div>
  );
}
