import { api } from "./api.js";
export async function loadAdmin() {
  const stats = await api("/admin/stats"); const events = await api("/admin/events");
  return { stats, events };
}
export async function createEvent(body) { return api("/admin/events", { method: "POST", body }); }
export async function recompute() { return api("/pricing/recompute", { method: "POST" }); }
