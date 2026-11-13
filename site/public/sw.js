// Retire the old offline shell without touching other projects on this origin.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key.startsWith("fvps-shell-"))
      .map((key) => caches.delete(key)));
    await self.registration.unregister();
  })());
});
