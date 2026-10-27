import { api } from "./api.js";
export async function holdAndConfirm(spotId, start, end) {
  const held = await api("/bookings/hold", { method: "POST", body: { spot_id: spotId, start, end } });
  const confirmed = await api(`/bookings/${held.id}/confirm`, { method: "POST", body: { payment_method: "mock_card" } });
  location.href = `/booking.html?id=${confirmed.id}`;
  return confirmed;
}
export async function loadBooking(id) { return api(`/bookings/${id}`); }
export async function cancelBooking(id) { return api(`/bookings/${id}/cancel`, { method: "POST" }); }
