/* Minimal service worker for diag.html's registration probe.
 * Its only job is to exist and install, so that "can this platform register a
 * service worker at all?" is answerable without guessing.
 */
self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
