/* juan of bike IA — service worker.
 * Purpose: receive notifications posted from the app via
 *   swReg.showNotification(title, options)
 * and, when installed as a PWA, keep displaying them after the tab is closed
 * (iOS 16.4+ / Android). No push server needed.
 */

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// When the user taps a notification, focus or open the app.
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil((async () => {
    const allClients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const client of allClients) {
      if ('focus' in client) {
        try { return client.focus(); } catch { /* ignore */ }
      }
    }
    if (self.clients.openWindow) {
      return self.clients.openWindow('/');
    }
  })());
});

/* Future: web-push endpoint — left as a stub so the integration is trivial
 * whenever you decide to wire VAPID + self.addEventListener('push', ...).
 */
