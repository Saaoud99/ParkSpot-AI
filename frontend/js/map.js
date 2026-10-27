import { api, publicConfig } from "./api.js";
let map, markers = {};
export async function initMap(containerId) {
  const cfg = await publicConfig();
  const center = [cfg.demo_center.lng, cfg.demo_center.lat];
  const div = document.getElementById(containerId);
  if (window.mapboxgl && cfg.mapbox_access_token) {
    mapboxgl.accessToken = cfg.mapbox_access_token;
    map = new mapboxgl.Map({ container: containerId, style: "mapbox://styles/mapbox/streets-v12", center, zoom: 13, antialias: true });
    map.addControl(new mapboxgl.NavigationControl(), "top-right");
    map.addControl(new mapboxgl.GeolocateControl({ trackUserLocation: false }), "top-right");
    map.on("load", () => map.resize());
  } else {
    div.innerHTML = `<div class="map-fallback"><div><div style="font-size:34px" aria-hidden="true">🗺️</div>
      <p><b>Interactive map unavailable</b><br>Add <span class="mono">MAPBOX_ACCESS_TOKEN</span> to <span class="mono">.env</span> to enable it.<br>
      Search results, booking and the AI assistant work fully without it.</p>
      <p class="mono" style="color:var(--ink-3)">${center[1]}, ${center[0]}</p></div></div>`;
    map = null;
  }
  const legend = document.createElement("div");
  legend.className = "map-legend"; legend.setAttribute("aria-label", "Map legend");
  legend.innerHTML = `<span class="pill pill-go">Available</span><span class="pill pill-hold">Held</span><span class="pill pill-stop">Occupied</span>`;
  div.parentElement.appendChild(legend);
  window.addEventListener("spot-selected", e => highlightMarker(e.detail));
  return cfg;
}
export function highlightMarker(id) {
  Object.entries(markers).forEach(([mid, m]) => m.getElement().classList.toggle("selected", Number(mid) === id));
  const m = markers[id];
  if (m && map) map.flyTo({ center: m.getLngLat(), zoom: Math.max(map.getZoom(), 14), duration: 700 });
}
export function renderMarkers(spots, onClick) {
  Object.values(markers).forEach(m => m.remove()); markers = {};
  if (!map || !window.mapboxgl) return;
  spots.forEach(s => {
    const dot = document.createElement("div");
    dot.className = "price-marker" + (s.status === "occupied" ? " occupied" : "");
    dot.textContent = `$${Number(s.price_per_hour_now).toFixed(0)}`;
    dot.title = `${s.title} — $${s.price_per_hour_now}/hr`;
    const m = new mapboxgl.Marker(dot).setLngLat([s.longitude, s.latitude])
      .setPopup(new mapboxgl.Popup({ offset: 18 }).setHTML(`<div><b>${s.title}</b><br>${s.address}<br><b>$${s.price_per_hour_now}/hr</b> · est $${s.estimated_total}</div>`))
      .addTo(map);
    dot.onclick = () => { highlightMarker(s.id); window.dispatchEvent(new CustomEvent("spot-selected", { detail: s.id })); onClick(s); };
    markers[s.id] = m;
  });
}
export async function searchAndRender(lat, lng, params, onClick) {
  const q = new URLSearchParams({ lat, lng, ...params });
  const spots = await api(`/spots/search?${q}`);
  renderMarkers(spots, onClick);
  return spots;
}
