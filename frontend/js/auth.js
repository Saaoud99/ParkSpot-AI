import { api } from "./api.js";
export function saveTokens(t) { localStorage.setItem("access_token", t.access_token); localStorage.setItem("refresh_token", t.refresh_token); }
export function logout() { localStorage.clear(); location.href = "/login.html"; }
export async function me() { return api("/auth/me"); }
export function requireAuth() { if (!localStorage.getItem("access_token")) location.href = "/login.html"; }
