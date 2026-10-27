export function el(id) { return document.getElementById(id); }
export function showMsg(id, text, ok = true) { const n = el(id); if (n) { n.textContent = text; n.className = ok ? "text-green-700" : "text-red-600"; } }
export function fmtMoney(v, cur = "USD") { return `${cur} ${Number(v).toFixed(2)}`; }
export function spotCard(s, onBook) {
  const d = document.createElement("div"); d.className = "card mb-3";
  d.innerHTML = `<b>${s.title}</b> — ${s.distance_km} km<br>${s.address}<br>$${s.price_per_hour_now}/h · est $${s.estimated_total} ${s.is_covered ? "· covered" : ""} ${s.has_ev_charging ? "· EV" : ""}`;
  const b = document.createElement("button"); b.className = "btn mt-2"; b.textContent = "Book";
  b.onclick = () => onBook(s); d.appendChild(b); return d;
}
