const BASE = "/api/v1";
export function token() { return localStorage.getItem("access_token"); }
export async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (token()) headers["Authorization"] = `Bearer ${token()}`;
  if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(BASE + path, { ...opts, headers });
  if (!res.ok) { let d = {}; try { d = await res.json(); } catch {} throw new Error(d.detail || res.statusText); }
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res;
}
export async function publicConfig() { return api("/config/public"); }
