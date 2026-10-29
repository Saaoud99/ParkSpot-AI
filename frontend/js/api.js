// API base URL. Default is same-origin relative ("/api/v1"): the FastAPI
// server serves both the frontend and the API, so this works on desktop,
// on a phone browser via the machine's LAN address (http://192.168.x.x:8000),
// and in hosted previews — with no code change. "127.0.0.1 refused to
// connect" on a phone means the *phone* was asked to reach its own
// loopback; the fix is opening the LAN/host address, not changing this.
// Only when the frontend is deliberately hosted separately from the API,
// set window.__PARKSPOT_API_BASE__ (e.g. via a small config script) or the
// <meta name="parkspot-api-base" content="https://api.example.com/api/v1">
// tag before this module loads. Never hardcode a dev LAN IP here.
const BASE = (typeof window !== "undefined" && (window.__PARKSPOT_API_BASE__ || document.querySelector('meta[name="parkspot-api-base"]')?.content)) || "/api/v1";
export function token() { return localStorage.getItem("access_token"); }

function handleUnauthorized() {
  // Expired/invalid session: clear ONLY ParkSpot auth state and send the
  // user to login with a way back — never trap them or loop.
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  const here = location.pathname;
  if (here.endsWith("login.html") || here.endsWith("register.html")) return;
  const next = encodeURIComponent(here + location.search);
  location.href = `/login.html?next=${next}&reason=expired`;
}

export async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (token()) headers["Authorization"] = `Bearer ${token()}`;
  if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(opts.body);
  }
  let res;
  try {
    res = await fetch(BASE + path, { ...opts, headers });
  } catch {
    throw new Error("Can't reach ParkSpot right now — check your connection and try again.");
  }
  if (res.status === 401 && !path.startsWith("/auth/")) {
    handleUnauthorized();
    throw new Error("Your session has expired — please log in again.");
  }
  if (!res.ok) {
    let d = {}; try { d = await res.json(); } catch {}
    // API errors are {detail, code}; validation detail is a sanitized list.
    const detail = Array.isArray(d.detail)
      ? d.detail.map(e => e.msg || "invalid value").join("; ")
      : (d.detail || `Request failed (${res.status})`);
    const err = new Error(detail); err.status = res.status; err.code = d.code; throw err;
  }
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res;
}
export async function publicConfig() { return api("/config/public"); }
