import { api } from "./api.js";
import { spotCard } from "./ui.js";
let sessionId = null;
export function initDrawer(openId, closeId, drawerId, scrimId) {
  const drawer = document.getElementById(drawerId), scrim = document.getElementById(scrimId);
  const open = () => { drawer.classList.add("open"); scrim.classList.add("open"); document.getElementById("chatin")?.focus(); };
  const close = () => { drawer.classList.remove("open"); scrim.classList.remove("open"); };
  if (openId) document.getElementById(openId).onclick = open;
  if (closeId) document.getElementById(closeId).onclick = close;
  if (scrim) scrim.onclick = close;
  document.addEventListener("keydown", e => { if (e.key === "Escape") close(); });
  return { open, close };
}
// Voice input via Web Speech API where the browser supports it; text input always remains available.
export function initVoice(buttonId, inputId, statusId) {
  const btn = document.getElementById(buttonId), input = document.getElementById(inputId), status = document.getElementById(statusId);
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Rec) { if (btn) btn.style.display = "none"; return; }
  const rec = new Rec(); rec.lang = "en-US"; rec.interimResults = false;
  let listening = false;
  rec.onresult = e => { input.value = e.results[0][0].transcript; input.focus(); };
  rec.onerror = e => { if (status) status.textContent = e.error === "not-allowed" ? "Microphone blocked — check browser permission, or just type." : "Voice input unavailable — please type."; };
  rec.onend = () => { listening = false; btn.textContent = "🎤"; btn.setAttribute("aria-label", "Start voice input"); if (status) status.textContent = ""; };
  btn.onclick = () => {
    if (listening) { rec.stop(); return; }
    try { rec.start(); listening = true; btn.textContent = "⏹"; btn.setAttribute("aria-label", "Stop voice input"); if (status) status.textContent = "Listening… speak now."; }
    catch { if (status) status.textContent = "Voice input unavailable — please type."; }
  };
}
export function initChat(logId, inputId, sendId, onBook) {
  const log = document.getElementById(logId), input = document.getElementById(inputId);
  function bubble(text, who) { const d = document.createElement("div"); d.className = `msg ${who}`; d.textContent = text; log.appendChild(d); log.scrollTop = log.scrollHeight; return d; }
  bubble("Hi! I can find real, available parking from live listings. Try: “covered parking near downtown tomorrow 9am for 2 hours under $10”. I never invent spots or prices — everything comes from the listings.", "msg-bot");
  async function send(textOverride) {
    const text = (textOverride ?? input.value).trim(); if (!text) return; input.value = "";
    bubble(text, "msg-user");
    const typing = bubble("", "msg-bot"); typing.innerHTML = `<span class="typing" aria-label="Assistant is thinking"><i></i><i></i><i></i></span>`;
    try {
      const loc = window._demoLocation || null;
      const res = await api("/chat", { method: "POST", body: { message: text, session_id: sessionId, location: loc, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone } });
      sessionId = res.session_id; typing.remove();
      bubble(res.reply + (res.degraded ? " (Assistant is offline right now — you can still book from the map.)" : ""), "msg-bot");
      if (res.spots && res.spots.length) {
        const wrap = document.createElement("div");
        res.spots.slice(0, 3).forEach(sp => wrap.appendChild(spotCard(
          { ...sp, status: "available", distance_km: sp.distance_km ?? null },
          s => onBook && onBook(s),
        )));
        log.appendChild(wrap);
      } else if (res.spots) {
        bubble("No parking matched that request. Try a wider area, different times, or a higher budget.", "msg-bot");
      }
      if (res.booking) { const d = bubble(`Booking #${res.booking.id} — ${res.booking.status}, total $${res.booking.total_price}.`, "msg-bot"); const a = document.createElement("a"); a.href = `/booking.html?id=${res.booking.id}`; a.textContent = " View booking & QR →"; a.style.fontWeight = "700"; d.appendChild(a); }
    } catch (e) {
      typing.remove();
      const d = bubble(`Something went wrong: ${e.message}.`, "msg-bot");
      const r = document.createElement("button"); r.className = "chip"; r.textContent = "↻ Retry"; r.onclick = () => send(text); d.appendChild(document.createElement("br")); d.appendChild(r);
    }
    log.scrollTop = log.scrollHeight;
  }
  document.getElementById(sendId).onclick = () => send();
  input.addEventListener("keydown", e => { if (e.key === "Enter") send(); });
  document.querySelectorAll("[data-chip]").forEach(c => c.onclick = () => send(c.dataset.chip));
}
