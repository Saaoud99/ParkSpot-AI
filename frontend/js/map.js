import { api, publicConfig } from "./api.js";
let map, markers = [];
export async function initMap(containerId, onMarker) {
  const cfg = await publicConfig();
  const center = [cfg.demo_center.lng, cfg.demo_center.lat];
  if (window.mapboxgl && cfg.mapbox_access_token) {
    mapboxgl.accessToken = cfg.mapbox_access_token;
    map = new mapboxgl.Map({ container: containerId, style: "mapbox://styles/mapbox/streets-v12", center, zoom: 13 });
  } else {
    const div = document.getElementById(containerId);
    div.innerHTML = "<p class='p-4'>Mapbox token not configured — list view below still works. Demo center: " + center.reverse().join(", ") + "</p>";
    map = null;
  }
  return cfg;
}
export function renderMarkers(spots, onClick) {
  markers.forEach(m => m.remove && m.remove()); markers = [];
  if (!map || !window.mapboxgl) return;
  spots.forEach(s => {
    const dot = document.createElement("div"); dot.className = "marker-dot";
    dot.style.background = s.status === "occupied" ? "#dc2626" : "#16a34a";
    dot.title = s.title;
    const m = new mapboxgl.Marker(dot).setLngLat([s.longitude, s.latitude]).addTo(map);
    dot.onclick = () => onClick(s); markers.push(m);
  });
}
export async function searchAndRender(lat, lng, params, onClick) {
  const q = new URLSearchParams({ lat, lng, ...params });
  const spots = await api(`/spots/search?${q}`);
  renderMarkers(spots, onClick);
  return spots;
}
