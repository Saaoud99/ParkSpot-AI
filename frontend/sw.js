// ParkSpot service worker — caches ONLY the static app shell.
// Never caches /api/ responses (auth, bookings, live availability must stay fresh).
const CACHE = "parkspot-shell-v4";
const SHELL = ["/", "/index.html", "/login.html", "/register.html", "/booking.html", "/bookings.html", "/host.html", "/admin.html", "/css/app.css", "/manifest.webmanifest", "/icon.svg",
  "/js/api.js", "/js/auth.js", "/js/ui.js", "/js/map.js", "/js/chat.js", "/js/booking.js", "/js/host.js", "/js/admin.js", "/js/pwa.js"];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/") || url.origin !== location.origin) return;
  e.respondWith(
    fetch(e.request).then(res => { const copy = res.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); return res; })
      .catch(() => caches.match(e.request).then(hit => hit || caches.match("/index.html")))
  );
});
