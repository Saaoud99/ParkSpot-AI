const BASE = "/api/v1";
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
  if (!res.ok) { let d = {}; try { d = await res.json(); } catch {} throw new Error(d.detail || `Request failed (${res.status})`); }
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res;
}
export async function publicConfig() { return api("/config/public"); }
