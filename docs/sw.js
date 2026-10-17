// Сайт стал простой страницей, офлайн-кэш больше не нужен.
// Этот файл только чистит кэш от старой версии и снимает регистрацию.

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((key) => caches.delete(key)));
    await self.registration.unregister();
  })());
});
