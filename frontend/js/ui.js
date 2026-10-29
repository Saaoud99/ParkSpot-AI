export function el(id) { return document.getElementById(id); }
// Escape any server/user-supplied string before it enters innerHTML.
// Facility titles, addresses and instructions are partner-supplied data —
// treating them as raw HTML would be stored XSS.
export function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
export function showMsg(id, text, ok = true) { const n = el(id); if (n) { n.textContent = text; n.style.color = ok ? "var(--brand-dark)" : "var(--error)"; } }
export function fmtMoney(v, cur = "USD") { return `${cur} ${Number(v).toFixed(2)}`; }
export function toast(text, ok = true) {
  let t = el("toast");
  if (!t) { t = document.createElement("div"); t.id = "toast"; t.setAttribute("role", "status"); document.body.appendChild(t); }
  t.className = ok ? "" : "err"; t.textContent = text;
  requestAnimationFrame(() => t.classList.add("show"));
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 3600);
}
export function skeletons(container, n = 3) { container.innerHTML = ""; for (let i = 0; i < n; i++) { const d = document.createElement("div"); d.className = "skeleton"; container.appendChild(d); } }
export function emptyState(container, icon, title, body) {
  container.innerHTML = `<div class="card" style="text-align:center;padding:36px 20px"><div style="font-size:34px" aria-hidden="true">${esc(icon)}</div><h3 style="margin:8px 0 4px">${esc(title)}</h3><p style="color:var(--ink-2);margin:0">${esc(body)}</p></div>`;
}
const PILL = { available: "pill-go", held: "pill-hold", occupied: "pill-stop", unavailable: "pill-stop" };
let selectedId = null;
export function markSelected(id) {
  selectedId = id;
  document.querySelectorAll("[data-spot-card]").forEach(c => {
    const on = Number(c.dataset.spotCard) === id;
    c.style.borderColor = on ? "var(--brand)" : ""; c.style.boxShadow = on ? "0 0 0 3px rgba(22,132,91,.25), var(--shadow)" : "";
  });
  window.dispatchEvent(new CustomEvent("spot-selected", { detail: id }));
}
export function spotCard(s, onBook, onSelect) {
  const d = document.createElement("article");
  d.className = "card card-hover reveal spot-card"; d.style.marginBottom = "12px"; d.dataset.spotCard = s.id;
  d.setAttribute("tabindex", "0"); d.setAttribute("aria-label", `${s.title}, $${s.price_per_hour_now} per hour`);
  const status = s.status || "available";
  const amenities = [s.is_covered ? "Covered" : "Open-air", s.has_ev_charging ? "EV charging" : null, s.spot_type].filter(Boolean).join(" · ");
  const price = s.price_per_hour_now != null ? Number(s.price_per_hour_now).toFixed(2) : Number(s.base_price_per_hour || 0).toFixed(2);
  d.innerHTML = `
    <div class="facility-photo" role="img" aria-label="No facility photo provided yet for ${esc(s.title)}"><span aria-hidden="true">🅿️</span><small>Facility photo not yet provided</small></div>
    <div class="spot-card-body">
    <div style="display:flex;justify-content:space-between;gap:10px;align-items:start">
      <h3 style="margin:0;font-size:1.05rem">${esc(s.title)}</h3><span class="pill ${PILL[status] || "pill-go"}">${esc(status)}</span>
    </div>
    <p style="color:var(--ink-2);margin:6px 0">${esc(s.address)}${s.distance_km != null ? ` · ${esc(s.distance_km)} km away` : ""}</p>
    <p style="margin:4px 0;color:var(--ink-2);font-size:.9rem">${esc(amenities)}</p>
    ${s.spaces_available != null ? `<p style="margin:4px 0"><span class="pill pill-go">${esc(s.spaces_available)} ParkSpot space${s.spaces_available === 1 ? "" : "s"} left</span> <span style="color:var(--ink-3);font-size:.82rem">of ${esc(s.authorized_capacity ?? s.spaces_available)} authorized for ParkSpot bookings</span></p>` : ""}
    <details style="margin:8px 0"><summary style="cursor:pointer;color:var(--brand);font-weight:600">Details & access</summary>
      <p style="color:var(--ink-2);margin:6px 0">${esc(s.access_instructions || "Access instructions are provided after booking.")}<br>
      Cancellation: free cancellation before arrival via “Cancel booking” on your booking page (per booking terms shown at checkout).</p></details>
    <div style="display:flex;justify-content:space-between;align-items:end;margin-top:8px">
      <div><span class="mono" style="font-size:1.3rem;font-weight:700">$${price}</span><span style="color:var(--ink-3)">/hr</span></div>
      ${s.estimated_total != null ? `<div style="color:var(--ink-2);font-size:.85rem">est. total <span class="mono" style="color:var(--ink);font-weight:700">$${Number(s.estimated_total).toFixed(2)}</span></div>` : ""}
    </div>
    </div>`;
  const row = document.createElement("div");
  row.className = "spot-card-actions";
  row.style.cssText = "display:flex;gap:8px;margin-top:12px";
  const view = document.createElement("a");
  view.className = "btn btn-ghost"; view.style.flex = "1"; view.textContent = "View facility";
  view.href = `/spot.html?id=${encodeURIComponent(s.id)}`;
  view.onclick = e => e.stopPropagation();
  const b = document.createElement("button"); b.className = "btn"; b.style.flex = "1"; b.textContent = "Review & reserve →";
  b.onclick = e => { e.stopPropagation(); onBook(s); };
  row.appendChild(view); row.appendChild(b);
  d.onclick = () => { markSelected(s.id); if (onSelect) onSelect(s); };
  d.onkeydown = e => { if (e.key === "Enter") { markSelected(s.id); if (onSelect) onSelect(s); } };
  d.appendChild(row); return d;
}
