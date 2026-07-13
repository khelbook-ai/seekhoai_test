import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api.js";

// Left navigation sidebar (spec 07 §0). Lists all courses (state persisted server-side)
// and lets the tester jump back and forth between stages — including the questions.
const STAGE_FOR_STATUS = (s) =>
  ["intake", "awaiting_clarification"].includes(s) ? "clarify"
  : s === "awaiting_cost" ? "cost"
  : "population";

function courseHref(id, stage) {
  return stage === "clarify" ? `/course/${id}/clarify`
    : stage === "cost" ? `/course/${id}/cost`
    : stage === "learn" ? `/learn/${id}`
    : stage === "dashboard" ? `/course/${id}/dashboard`
    : `/course/${id}`;
}

export default function Sidebar({ user, onSignOut }) {
  const nav = useNavigate();
  const loc = useLocation();
  const [courses, setCourses] = useState([]);

  // active course id from the current URL (/course/:id/... or /learn/:id)
  const m = loc.pathname.match(/\/(?:course|learn)\/([0-9a-f-]{36})/);
  const activeId = m ? m[1] : null;

  useEffect(() => {
    let live = true;
    const load = () => api.listCourses().then((d) => live && setCourses(d.courses)).catch(() => {});
    load();
    const t = setInterval(load, 8000); // reflect build-status changes
    return () => { live = false; clearInterval(t); };
  }, [loc.pathname]);

  const active = courses.find((c) => c.course_id === activeId);
  const st = active?.status;
  const built = st === "built";
  const pastIntake = active && !["intake"].includes(st);

  const Stage = ({ to, label, enabled, here }) => (
    <button className={"stage" + (here ? " here" : "")} disabled={!enabled}
      onClick={() => nav(courseHref(activeId, to))}>{label}</button>
  );

  return (
    <aside className="sidebar">
      <div className="brand" onClick={() => nav("/")}>Seekhai</div>
      {user && (
        <div className="whoami">
          <span>👤 {user.name}</span>
          <button className="link" onClick={onSignOut}>switch</button>
        </div>
      )}
      <button className="newbtn" onClick={() => nav("/")}>+ New course</button>
      <button className={"stage" + (loc.pathname === "/me" ? " here" : "")}
        style={{ width: "100%", textAlign: "left" }} onClick={() => nav("/me")}>
        📊 My learning data
      </button>

      <div className="sec">Your courses</div>
      {courses.length === 0 && <p className="note">No courses yet.</p>}
      {courses.map((c) => (
        <div key={c.course_id}>
          <div className={"course-item" + (c.course_id === activeId ? " active" : "")}
            onClick={() => nav(courseHref(c.course_id, STAGE_FOR_STATUS(c.status)))}
            title={c.course_id}>
            <span>{c.title?.slice(0, 34) || "Untitled"}</span>
            <span className="st">{c.status}</span>
          </div>
          {c.course_id === activeId && (
            <div className="stages">
              <Stage to="clarify" label="Student Input" enabled={pastIntake || st === "awaiting_clarification"}
                here={loc.pathname.endsWith("/clarify")} />
              <Stage to="cost" label="Cost & curriculum" enabled={!!active && st !== "intake" && st !== "awaiting_clarification"}
                here={loc.pathname.endsWith("/cost")} />
              <Stage to="population" label="Content / build" enabled={["building", "built", "failed"].includes(st)}
                here={loc.pathname === `/course/${activeId}`} />
              <Stage to="learn" label="Learn" enabled={built} here={loc.pathname.startsWith("/learn/")} />
              <Stage to="dashboard" label="Dashboard" enabled={built} here={loc.pathname.endsWith("/dashboard")} />
            </div>
          )}
        </div>
      ))}
    </aside>
  );
}
