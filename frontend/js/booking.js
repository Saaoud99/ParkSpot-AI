import { api } from "./api.js";
// Booking flow is two real backend steps: hold (free, 10-min expiry) -> review -> confirm (mock payment on server).
export async function createHold(spotId, start, end) {
  return api("/bookings/hold", { method: "POST", body: { spot_id: spotId, start, end } });
}
export async function confirmBooking(id) {
  return api(`/bookings/${id}/confirm`, { method: "POST", body: { payment_method: "mock_card" } });
}
export async function holdAndConfirm(spotId, start, end) {
  const held = await createHold(spotId, start, end);
  return confirmBooking(held.id);
}
export async function loadBooking(id) { return api(`/bookings/${id}`); }
export async function cancelBooking(id) { return api(`/bookings/${id}/cancel`, { method: "POST" }); }
