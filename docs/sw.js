/* Офлайн-оболочка сайта.

   Кэшируем только саму страницу: список узлов и подписки лежат в другом
   домене (raw.githubusercontent) и меняются каждый час, поэтому их не
   трогаем вообще — иначе браузер покажет вчерашние серверы. */

// Имя кэша — это версия оболочки. Меняете index.html, styles.css или
// app.js — поднимите номер, иначе у вернувшихся посетителей останется
// старая копия страницы.
const CACHE = "fvps-shell-v7";

const SHELL = [
  "./",
  "index.html",
  "styles.css",
  "app.js",
  "favicon.svg",
  "manifest.webmanifest",
  "vendor/qrcode.min.js",
  "assets/icon-192.png",
  "assets/icon-512.png",
  "assets/ton-qr.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      // Один недоступный файл не должен ломать установку целиком.
      Promise.all(SHELL.map((path) => cache.add(path).catch(() => {})))
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  // Данные подписки и всё внешнее отдаём браузеру как есть.
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request).then((response) => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
        }
        return response;
      }).catch(() => cached || Response.error());

      // Оболочка: сначала кэш, в фоне обновляем.
      return cached || network;
    })
  );
});
