import { api } from "./api.js";
export async function loadHost() {
  const spots = await api("/spots/mine"); const bookings = await api("/bookings/host?limit=50");
  return { spots, bookings: bookings.items };
}
export async function createSpot(body) { return api("/spots", { method: "POST", body }); }
export async function simulate(cameraId, event, plate) { return api("/vision/simulate", { method: "POST", body: { camera_id: cameraId, event, plate } }); }
export async function loadEvents(spotId) { return api(`/vision/events?spot_id=${spotId}`); }
