import { api } from "./api.js";
export function saveTokens(t) { localStorage.setItem("access_token", t.access_token); localStorage.setItem("refresh_token", t.refresh_token); }
export function clearSession() { localStorage.removeItem("access_token"); localStorage.removeItem("refresh_token"); }
export function logout() { clearSession(); location.href = "/index.html"; }
export async function me() { return api("/auth/me"); }
export function isLoggedIn() { return !!localStorage.getItem("access_token"); }
// Only allow same-site relative paths as post-login destinations (no open redirects).
export function safeNext(fallback = "/index.html") {
  const next = new URLSearchParams(location.search).get("next");
  if (next && next.startsWith("/") && !next.startsWith("//")) return next;
  return fallback;
}
export function requireAuth() {
  if (!isLoggedIn()) {
    const next = encodeURIComponent(location.pathname + location.search);
    location.href = `/login.html?next=${next}`;
    return false;
  }
  return true;
}
