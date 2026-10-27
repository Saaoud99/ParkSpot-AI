import { api } from "./api.js";
let sessionId = null;
export function initChat(logId, inputId, sendId, onSpots) {
  const log = document.getElementById(logId), input = document.getElementById(inputId);
  async function send() {
    const text = input.value.trim(); if (!text) return; input.value = "";
    log.innerHTML += `<div><b>You:</b> ${text}</div>`;
    try {
      const loc = window._demoLocation || null;
      const res = await api("/chat", { method: "POST", body: { message: text, session_id: sessionId, location: loc, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone } });
      sessionId = res.session_id;
      log.innerHTML += `<div><b>ParkSpot:</b> ${res.reply}</div>`;
      if (res.spots && onSpots) onSpots(res.spots);
      if (res.booking) log.innerHTML += `<div>Booking #${res.booking.id} — ${res.booking.status} <a class="text-blue-600 underline" href="/booking.html?id=${res.booking.id}">View / QR</a></div>`;
    } catch (e) { log.innerHTML += `<div class="text-red-600">${e.message}</div>`; }
    log.scrollTop = log.scrollHeight;
  }
  document.getElementById(sendId).onclick = send;
  input.addEventListener("keydown", e => { if (e.key === "Enter") send(); });
}
