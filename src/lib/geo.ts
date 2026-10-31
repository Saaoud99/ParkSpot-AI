/** GPS helpers for "Parking Near Me" (web Geolocation API).
 *
 * Location is requested ONLY from an explicit user tap, foreground,
 * one-time — never on launch, never tracked, never stored. Coordinates
 * are used only to rank real facility inventory by real distance.
 */

export type GeoErrorKind = "denied" | "unavailable" | "timeout" | "unsupported" | "insecure";

export class GeoError extends Error {
  kind: GeoErrorKind;
  constructor(kind: GeoErrorKind) {
    super(kind);
    this.kind = kind;
  }
}

export function haversineMeters(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6_371_000;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dphi = ((lat2 - lat1) * Math.PI) / 180;
  const dlmb = ((lng2 - lng1) * Math.PI) / 180;
  const a = Math.sin(dphi / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dlmb / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

export function formatDistance(m: number, lang: "en" | "ar"): string {
  if (m < 1000) return lang === "ar" ? `${Math.round(m)} م` : `${Math.round(m)} m`;
  const km = m / 1000;
  return lang === "ar" ? `${km.toFixed(1)} كم` : `${km.toFixed(1)} km`;
}

/** One-time foreground position. Rejects with a typed GeoError — never invents coordinates. */
export function getCurrentPositionOnce(timeoutMs = 12_000): Promise<{ lat: number; lng: number; accuracy?: number }> {
  return new Promise((resolve, reject) => {
    if (typeof window === "undefined" || !("geolocation" in navigator)) {
      reject(new GeoError("unsupported"));
      return;
    }
    if (!window.isSecureContext) {
      reject(new GeoError("insecure")); // browsers only allow geolocation on HTTPS/localhost
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: pos.coords.accuracy }),
      (err) => {
        if (err.code === err.PERMISSION_DENIED) reject(new GeoError("denied"));
        else if (err.code === err.TIMEOUT) reject(new GeoError("timeout"));
        else reject(new GeoError("unavailable"));
      },
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 60_000 },
    );
  });
}
