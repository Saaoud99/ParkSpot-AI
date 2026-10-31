import { supabase } from "@/integrations/supabase/client";

/**
 * Client for the ParkSpot Meta backend (FastAPI, app/meta).
 *
 * VITE_META_API_URL points at that backend, e.g. http://localhost:8080.
 * It is a public URL, not a secret — all Meta credentials stay in the
 * backend `.env`. When the URL is unset, every call throws and the UI
 * degrades gracefully (manual search and the existing chat keep working).
 */
const RAW_BASE = ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_META_API_URL ?? "").replace(/\/$/, "");

/**
 * If the configured backend points at localhost but the page itself was
 * opened via a LAN IP / hostname (e.g. http://10.1.19.4:8080 from a phone),
 * "localhost" would resolve to the phone — rewrite the host to the page's
 * host (same backend port on the dev machine). No-op on desktop localhost.
 */
function resolveBase(): string {
  if (!RAW_BASE || typeof window === "undefined") return RAW_BASE;
  try {
    const url = new URL(RAW_BASE);
    const pageHost = window.location.hostname;
    if ((url.hostname === "localhost" || url.hostname === "127.0.0.1") && pageHost && pageHost !== "localhost" && pageHost !== "127.0.0.1") {
      url.hostname = pageHost;
      return url.toString().replace(/\/$/, "");
    }
  } catch { /* keep raw value */ }
  return RAW_BASE;
}

const BASE = resolveBase();

export const metaBase = BASE;
export const metaAuthHeaders = authHeaders;
export const metaUnwrap = unwrap;

export const metaBackendConfigured = () => BASE.length > 0;

export type MetaStatus = { assistant: string; vision_sam: string; voice: string; voice_flag_on?: boolean; voice_key_present?: boolean; voice_max_seconds?: number; voice_max_upload_mb?: number };

/** Recording cap shared by all microphone UIs: backend-configured, 30 s safe default. */
export function voiceMaxSeconds(status?: MetaStatus | null): number {
  const v = Number(status?.voice_max_seconds);
  return Number.isFinite(v) && v > 0 ? Math.min(600, Math.max(5, v)) : 30;
}

const VOICE_FILENAMES: Record<string, string> = {
  "audio/wav": "voice.wav", "audio/x-wav": "voice.wav",
  "audio/webm": "voice.webm", "audio/mp4": "voice.mp4", "audio/x-m4a": "voice.m4a",
  "audio/mpeg": "voice.mp3", "audio/ogg": "voice.ogg", "audio/aac": "voice.aac",
};

/** Filename matching the actual MediaRecorder Blob type (never a hardcoded container). */
export function voiceUploadFilename(blob: Blob): string {
  const type = (blob.type || "").split(";")[0].trim().toLowerCase();
  return VOICE_FILENAMES[type] ?? "voice.webm";
}

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error("not-signed-in");
  return { Authorization: `Bearer ${token}` };
}

async function unwrap(res: Response) {
  if (res.ok) return res.json();
  let message = `Error ${res.status}`;
  try {
    const body = await res.json();
    message = body?.error?.message ?? message;
  } catch { /* keep default */ }
  throw new Error(message);
}

export async function fetchMetaStatus(): Promise<MetaStatus> {
  if (!metaBackendConfigured()) throw new Error("meta-backend-not-configured");
  return unwrap(await fetch(`${BASE}/api/v1/meta/status`));
}

export type MetaFacility = {
  id: string; name: string; name_ar?: string | null; city: string; address: string;
  price_mad_per_hour: number; available: number; capacity: number;
  features: string[]; rating?: number | null;
};

export async function metaChat(messages: { role: string; content: string }[], lang: string): Promise<{ reply: string; facilities: MetaFacility[]; mode?: string; model?: string }> {
  if (!metaBackendConfigured()) throw new Error("meta-backend-not-configured");
  return unwrap(await fetch(`${BASE}/api/v1/meta/assistant/chat`, {
    method: "POST",
    headers: { "content-type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ messages, lang }),
  }));
}

export async function metaTranscribe(audio: Blob, lang: string): Promise<{ text: string }> {
  if (!metaBackendConfigured()) throw new Error("meta-backend-not-configured");
  const form = new FormData();
  form.append("audio", audio, voiceUploadFilename(audio));
  form.append("language", lang);
  return unwrap(await fetch(`${BASE}/api/v1/meta/voice/transcribe`, { method: "POST", headers: await authHeaders(), body: form }));
}

export type NearbyFacility = MetaFacility & { lat: number; lng: number; distance_meters: number };

export async function metaNearbySpots(lat: number, lng: number, radiusKm?: number): Promise<NearbyFacility[]> {
  if (!metaBackendConfigured()) throw new Error("meta-backend-not-configured");
  const qs = new URLSearchParams({ lat: String(lat), lng: String(lng) });
  if (radiusKm) qs.set("radius_km", String(radiusKm));
  const out = await unwrap(await fetch(`${BASE}/api/v1/meta/spots/nearby?${qs}`, { headers: await authHeaders() }));
  return (out.facilities ?? []) as NearbyFacility[];
}

export type VisionResult = {
  vehicles_detected: number;
  plate: string | null;
  ocr_confidence: number;
  ocr_accepted: boolean;
  access: string;
  reason?: string;
  verified_booking?: { booking_id: string; facility_id: string } | null;
  source: string;
};

export async function metaVisionAnalyze(image: Blob, facilityId?: string, opts?: { cameraId?: string; simulated?: boolean }): Promise<VisionResult> {
  if (!metaBackendConfigured()) throw new Error("meta-backend-not-configured");
  const form = new FormData();
  form.append("image", image, "frame.jpg");
  if (facilityId) form.append("facility_id", facilityId);
  if (opts?.cameraId) form.append("camera_id", opts.cameraId);
  if (opts?.simulated) form.append("simulated", "true");
  return unwrap(await fetch(`${BASE}/api/v1/meta/vision/analyze`, { method: "POST", headers: await authHeaders(), body: form }));
}
