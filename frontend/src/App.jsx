import React from "react";
import { Routes, Route, Outlet } from "react-router-dom";
import Sidebar from "./components/Sidebar.jsx";
import CourseCreation from "./screens/CourseCreation.jsx";
import Clarification from "./screens/Clarification.jsx";
import CostApproval from "./screens/CostApproval.jsx";
import Population from "./screens/Population.jsx";
import Learning from "./screens/Learning.jsx";
import Dashboard from "./screens/Dashboard.jsx";

function Layout() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main"><Outlet /></div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<CourseCreation />} />
        <Route path="/course/:courseId/clarify" element={<Clarification />} />
        <Route path="/course/:courseId/cost" element={<CostApproval />} />
        <Route path="/course/:courseId" element={<Population />} />
        <Route path="/learn/:courseId" element={<Learning />} />
        <Route path="/course/:courseId/dashboard" element={<Dashboard />} />
      </Route>
    </Routes>
  );
}
