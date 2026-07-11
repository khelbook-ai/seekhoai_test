import React from "react";
import { Routes, Route } from "react-router-dom";
import CourseCreation from "./screens/CourseCreation.jsx";
import Clarification from "./screens/Clarification.jsx";
import CostApproval from "./screens/CostApproval.jsx";
import Population from "./screens/Population.jsx";
import Learning from "./screens/Learning.jsx";
import Dashboard from "./screens/Dashboard.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<CourseCreation />} />
      <Route path="/course/:courseId/clarify" element={<Clarification />} />
      <Route path="/course/:courseId/cost" element={<CostApproval />} />
      <Route path="/course/:courseId" element={<Population />} />
      <Route path="/learn/:courseId" element={<Learning />} />
      <Route path="/course/:courseId/dashboard" element={<Dashboard />} />
    </Routes>
  );
}
