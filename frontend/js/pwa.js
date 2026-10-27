// Registers the service worker and surfaces offline state. Loaded as a classic script on every page.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
window.addEventListener("offline", () => {
  const b = document.createElement("div");
  b.id = "offline-bar";
  b.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:90;background:#FFF4E0;color:#8A5A00;text-align:center;padding:8px;font:600 .85rem Inter,system-ui,sans-serif;border-bottom:1px solid #F0D9A8";
  b.textContent = "You're offline — live availability, booking and the AI assistant need a connection.";
  document.body.appendChild(b);
});
window.addEventListener("online", () => { const b = document.getElementById("offline-bar"); if (b) b.remove(); });
