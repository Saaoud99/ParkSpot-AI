import { useEffect, useRef } from "react";
import type { Facility } from "./FacilityCard";

export default function ParkingMap({ facilities, onSelect }: { facilities: Facility[]; onSelect: (id: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let map: import("leaflet").Map | undefined;
    let cancelled = false;
    (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !ref.current) return;
      map = L.map(ref.current, { zoomControl: false }).setView([33.59, -7.62], 12);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors", maxZoom: 19,
      }).addTo(map);
      for (const f of facilities) {
        const icon = L.divIcon({
          className: "", iconSize: [64, 32], iconAnchor: [32, 16],
          html: `<div style="background:${f.available > 0 ? "#1f5a3f" : "#b4412f"};color:#fff;font:600 12px 'Plus Jakarta Sans';padding:6px 10px;border-radius:999px;border:2px solid #fff;box-shadow:0 6px 16px rgba(0,0,0,.25);white-space:nowrap">P · ${(f.price_per_hour_cents / 100).toFixed(0)}</div>`,
        });
        L.marker([f.lat, f.lng], { icon }).addTo(map).on("click", () => onSelect(f.id));
      }
      if (facilities.length) map.fitBounds(facilities.filter((f) => f.city === "Casablanca").map((f) => [f.lat, f.lng]) as [number, number][], { padding: [40, 40] });
    })();
    return () => { cancelled = true; map?.remove(); };
  }, [facilities, onSelect]);
  return <div ref={ref} className="h-full w-full" />;
}
