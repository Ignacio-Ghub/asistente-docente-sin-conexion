// Permite abrir el asistente sin conexión: guarda la página y la usa cuando no hay internet.
// Las respuestas de /api nunca se guardan (las genera el modelo y necesitan conexión).
const CACHE = 'asistente-v2';
const BASE = ['/', '/logo-jiba-azul.png', '/manifest.webmanifest', '/icono-192.png', '/icono-512.png', '/apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(BASE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.pathname.startsWith('/api/')) return;
  // Primero la red (para recibir siempre la última versión); sin conexión, la copia guardada.
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok || r.type === 'opaque') { const copia = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copia)); }
    return r;
  }).catch(() => caches.match(e.request, {ignoreSearch: true}).then(r => r || caches.match('/'))));
});
