import React, { useState } from "react";

// Drag-drop architecture diagram (spec 04 §1). Drag an entity into a labelled box (native
// HTML5 drag-and-drop), or tap an entity then tap a box (touch fallback). `value` is a
// { box_id: entity_id } mapping. Graded all-or-nothing like an MCQ.
export default function ArchDiagram({ payload, value, onChange, decided, solution, readonly }) {
  const boxes = payload.boxes || [];
  const entities = payload.entities || [];
  const byId = Object.fromEntries(entities.map((e) => [e.id, e]));
  const mapping = value || {};
  const placed = new Set(Object.values(mapping));
  const correct = solution?.correct_mapping;
  const [pick, setPick] = useState(null);   // entity id selected via tap
  const [over, setOver] = useState(null);   // box id being dragged over

  const active = !decided && !readonly;
  function place(boxId, entId) {
    if (!active || !entId) return;
    const next = { ...mapping };
    for (const k of Object.keys(next)) if (next[k] === entId) delete next[k]; // move, don't duplicate
    next[boxId] = entId;
    onChange(next); setPick(null);
  }
  function unplace(boxId) {
    if (!active) return;
    const next = { ...mapping }; delete next[boxId]; onChange(next);
  }
  const tray = entities.filter((e) => !placed.has(e.id));

  return (
    <div className="arch">
      <div className="arch-boxes">
        {boxes.map((b) => {
          const ent = mapping[b.id] ? byId[mapping[b.id]] : null;
          let cls = "arch-box";
          if (over === b.id) cls += " over";
          if (decided && correct) cls += mapping[b.id] === correct[b.id] ? " ok" : " bad";
          return (
            <div key={b.id} className={cls}
              onDragOver={(e) => { if (active) { e.preventDefault(); setOver(b.id); } }}
              onDragLeave={() => setOver(null)}
              onDrop={(e) => { e.preventDefault(); setOver(null); place(b.id, e.dataTransfer.getData("text/entity")); }}
              onClick={() => (pick ? place(b.id, pick) : ent && unplace(b.id))}>
              <div className="arch-label">{b.label}</div>
              <div className="arch-slot">
                {ent ? <span className="chip placed" draggable={active}
                  onDragStart={(e) => e.dataTransfer.setData("text/entity", ent.id)}>{ent.text}</span>
                  : <span className="arch-hint">{active ? "drop here" : "—"}</span>}
              </div>
              {decided && correct && mapping[b.id] !== correct[b.id] && (
                <div className="arch-fix">✓ {byId[correct[b.id]]?.text}</div>
              )}
            </div>
          );
        })}
      </div>

      {active && (
        <div className="arch-tray">
          {tray.length === 0 && <span className="note">All placed — submit when ready.</span>}
          {tray.map((e) => (
            <span key={e.id} className={"chip" + (pick === e.id ? " sel" : "")} draggable
              onDragStart={(ev) => ev.dataTransfer.setData("text/entity", e.id)}
              onClick={() => setPick(pick === e.id ? null : e.id)}>{e.text}</span>
          ))}
        </div>
      )}
    </div>
  );
}
