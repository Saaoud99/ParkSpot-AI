import { metaAuthHeaders, metaBackendConfigured, metaBase, metaUnwrap } from "@/lib/meta";

/** Client for the Super Admin API (FastAPI /api/v1/admin/*).
 * Every call carries the admin's own Supabase JWT; the backend verifies
 * the admin role server-side on every request. No secrets live here. */

async function call(path: string, init?: RequestInit) {
  if (!metaBackendConfigured()) throw new Error("meta-backend-not-configured");
  const headers = {
    ...(await metaAuthHeaders()),
    ...(init?.body ? { "content-type": "application/json" } : {}),
  };
  return metaUnwrap(
    await fetch(`${metaBase}/api/v1/admin${path}`, {
      ...init,
      headers: { ...headers, ...(init?.headers ?? {}) },
    }),
  );
}

const get = (p: string) => call(p);
const post = (p: string, body?: unknown) =>
  call(p, { method: "POST", body: body ? JSON.stringify(body) : undefined });
const patch = (p: string, body: unknown) =>
  call(p, { method: "PATCH", body: JSON.stringify(body) });

export const adminApi = {
  overview: () => get("/overview"),
  users: (q: string) => get(`/users?${q}`),
  userDetail: (id: string) => get(`/users/${id}`),
  suspendUser: (id: string, reason: string) => post(`/users/${id}/suspend`, { reason }),
  reactivateUser: (id: string, reason: string) => post(`/users/${id}/reactivate`, { reason }),
  setRole: (id: string, role: string, action: "grant" | "revoke", reason: string) =>
    post(`/users/${id}/roles`, { role, action, reason }),
  facilities: () => get("/facilities"),
  createFacility: (body: unknown) => post("/facilities", body),
  updateFacility: (id: string, body: unknown) => patch(`/facilities/${id}`, body),
  setPrice: (id: string, price_per_hour_cents: number, reason: string) =>
    patch(`/facilities/${id}/price`, { price_per_hour_cents, reason }),
  pricing: () => get("/pricing"),
  bookings: (q: string) => get(`/bookings?${q}`),
  cancelBooking: (id: string, reason: string) => post(`/bookings/${id}/cancel`, { reason }),
  aiStatus: () => get("/ai/status"),
  aiHealth: (service: string) => post(`/ai/health/${service}`),
  aiToggle: (feature: string, enabled: boolean, reason: string) =>
    post("/ai/toggle", { feature, enabled, reason }),
  cameras: () => get("/cameras"),
  createCamera: (body: unknown) => post("/cameras", body),
  updateCamera: (id: string, body: unknown) => patch(`/cameras/${id}`, body),
  wallets: () => get("/wallets"),
  walletTx: (userId: string) => get(`/wallets/${userId}/transactions`),
  adjustWallet: (userId: string, amount_cents: number, reason: string) =>
    post(`/wallets/${userId}/adjust`, { amount_cents, reason }),
  reports: (days: number) => get(`/reports?days=${days}`),
  incidents: (status = "") => get(`/incidents${status ? `?status=${status}` : ""}`),
  createIncident: (body: unknown) => post("/incidents", body),
  updateIncident: (id: string, status: string, reason: string) =>
    patch(`/incidents/${id}`, { status, reason }),
  audit: (q: string) => get(`/audit?${q}`),
  settings: () => get("/settings"),
  updateSettings: (settings: Record<string, unknown>, reason: string) =>
    patch("/settings", { settings, reason }),
  csvUrl: () => `${metaBase}/api/v1/admin/reports/bookings.csv`,
};

export async function downloadCsv() {
  const res = await fetch(adminApi.csvUrl(), { headers: await metaAuthHeaders() });
  if (!res.ok) throw new Error(`Error ${res.status}`);
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "bookings.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}
