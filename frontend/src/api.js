// Thin API client. Vite proxies /api -> http://localhost:8000 (see vite.config.js).
async function j(res) {
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}
const post = (url, body) =>
  fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then(j);
const get = (url) => fetch(url).then(j);

// --- current user (simple name-only signup, spec 01 §5) --------------------
const USER_KEY = "seekhai_user";
export const currentUser = () => {
  try { return JSON.parse(localStorage.getItem(USER_KEY) || "null"); } catch { return null; }
};
export const setCurrentUser = (u) => localStorage.setItem(USER_KEY, JSON.stringify(u));
export const clearCurrentUser = () => localStorage.removeItem(USER_KEY);
const uid = () => currentUser()?.user_id || null;

export const api = {
  // users
  signup: (name) => post("/api/users", { name }),
  getUser: (id) => get(`/api/users/${id}`),
  dossier: (id = uid()) => get(`/api/users/${id}/dossier`),

  // build
  listCourses: () => get(`/api/courses${uid() ? `?user_id=${uid()}` : ""}`),
  buildEvents: (courseId, after = 0) => get(`/api/courses/${courseId}/events?after=${after}`),
  createCourse: (raw_prompt, raw_role) => post("/api/courses", { raw_prompt, raw_role, user_id: uid() }),
  clarify: (courseId, answers) => post(`/api/courses/${courseId}/clarify`, { answers }),
  getCourse: (courseId) => get(`/api/courses/${courseId}`),
  costApproval: (courseId, approved) => post(`/api/courses/${courseId}/cost-approval`, { approved }),
  population: (courseId) => get(`/api/courses/${courseId}/population`),
  illustrations: (courseId) => get(`/api/courses/${courseId}/illustrations`),
  restart: (courseId, mode) => post(`/api/courses/${courseId}/restart`, { mode, user_id: uid() }),

  // learning (resume-first: progress + score survive navigation)
  openSession: (courseId) => post(`/api/courses/${courseId}/open`, { user_id: uid() }),
  sessionMap: (sid) => get(`/api/sessions/${sid}/map`),
  reviewInteraction: (sid, interaction_id) => get(`/api/sessions/${sid}/review/${interaction_id}`),
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
  // one-click thumbs up/down, droppable anywhere (value: 1 up, -1 down)
  reaction: (target_kind, target_id, value, note) =>
    post("/api/feedback/reaction", { target_kind, target_id, value, note, user_id: uid() }),
};
