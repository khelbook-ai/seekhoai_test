import React, { useState } from "react";
import { Routes, Route, Outlet } from "react-router-dom";
import Sidebar from "./components/Sidebar.jsx";
import Signup from "./components/Signup.jsx";
import CourseCreation from "./screens/CourseCreation.jsx";
import Clarification from "./screens/Clarification.jsx";
import CostApproval from "./screens/CostApproval.jsx";
import Population from "./screens/Population.jsx";
import Learning from "./screens/Learning.jsx";
import Dashboard from "./screens/Dashboard.jsx";
import UserData from "./screens/UserData.jsx";
import { currentUser } from "./api.js";

function Layout({ user, onSignOut }) {
  return (
    <div className="app-shell">
      <Sidebar user={user} onSignOut={onSignOut} />
      <div className="app-main"><Outlet /></div>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(currentUser());

  // Name-only signup gate (spec 01 §5): everything downstream is scoped to this learner.
  if (!user) return <div className="app-shell"><div className="app-main"><Signup onDone={setUser} /></div></div>;

  const signOut = () => { localStorage.removeItem("seekhai_user"); setUser(null); };

  return (
    <Routes>
      <Route element={<Layout user={user} onSignOut={signOut} />}>
        <Route path="/" element={<CourseCreation />} />
        <Route path="/me" element={<UserData />} />
        <Route path="/course/:courseId/clarify" element={<Clarification />} />
        <Route path="/course/:courseId/cost" element={<CostApproval />} />
        <Route path="/course/:courseId" element={<Population />} />
        <Route path="/learn/:courseId" element={<Learning />} />
        <Route path="/course/:courseId/dashboard" element={<Dashboard />} />
      </Route>
    </Routes>
  );
}
