// Thin API client. Vite proxies /api -> http://localhost:8000 (see vite.config.js).
async function j(res) {
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}
const post = (url, body) =>
  fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then(j);
const get = (url) => fetch(url).then(j);

export const api = {
  // build
  createCourse: (raw_prompt, raw_role) => post("/api/courses", { raw_prompt, raw_role }),
  clarify: (courseId, answers) => post(`/api/courses/${courseId}/clarify`, { answers }),
  getCourse: (courseId) => get(`/api/courses/${courseId}`),
  costApproval: (courseId, approved) => post(`/api/courses/${courseId}/cost-approval`, { approved }),
  population: (courseId) => get(`/api/courses/${courseId}/population`),
  restart: (courseId, mode) => post(`/api/courses/${courseId}/restart`, { mode }),

  // learning
  createSession: (course_id, resume = false) => post("/api/sessions", { course_id, resume }),
  currentInteraction: (sid) => get(`/api/sessions/${sid}/interaction`),
  getHint: (sid, interaction_id, level) => post(`/api/sessions/${sid}/hint`, { interaction_id, level }),
  getContent: (sid, interaction_id) => post(`/api/sessions/${sid}/content`, { interaction_id }),
  submitAnswer: (sid, payload) => post(`/api/sessions/${sid}/answer`, payload),
  dashboard: (courseId, sid) => get(`/api/courses/${courseId}/dashboard${sid ? `?session_id=${sid}` : ""}`),

  // feedback
  contentFeedback: (interaction_id, feedback_md) => post("/api/feedback/content", { interaction_id, feedback_md }),
  contentFeedbackImage: (interaction_id, feedback_md, caption, file) => {
    const fd = new FormData();
    fd.append("interaction_id", interaction_id);
    fd.append("feedback_md", feedback_md);
    fd.append("caption", caption || "");
    fd.append("image", file);
    return fetch("/api/feedback/content/upload", { method: "POST", body: fd }).then(j);
  },
  appFeedback: (page_key, feedback_md) => post("/api/feedback/application", { page_key, feedback_md }),
};
