/**
 * Зеркало подписок free-vpn-sub для Cloudflare Workers.
 *
 * Зачем: raw.githubusercontent.com и сам GitHub Pages в России часто
 * недоступны. Воркер живёт на домене Cloudflare, который обычно открыт,
 * и отдаёт те же файлы.
 *
 * Что делать с кодом (всё в браузере, без установки чего-либо):
 *   1. Открой dash.cloudflare.com и войди (бесплатного аккаунта хватит).
 *   2. Workers & Pages -> Create -> Workers -> Start from scratch.
 *   3. Имя воркера, например free-vpn-sub.
 *   4. Вставь этот файл целиком вместо шаблона, нажми Deploy.
 *   5. Получишь адрес вида https://free-vpn-sub.ТВОЙ-АККАУНТ.workers.dev
 *
 * После этого:
 *   - https://free-vpn-sub.ТВОЙ-АККАУНТ.workers.dev/sub.txt это подписка;
 *   - адрес можно вписать в клиент напрямую;
 *   - добавь его в EXTRA_MIRRORS в docs/app.js, чтобы он появился на сайте.
 *
 * Бесплатный тариф это 100 000 запросов в сутки, для подписки хватает
 * с большим запасом. Файлы кэшируются на краю Cloudflare на 5 минут.
 */

const REPO = "sakazxc1400-creator/free-vpn-sub";
const BRANCH = "main";
const UPSTREAM = `https://raw.githubusercontent.com/${REPO}/${BRANCH}/output/`;
const FALLBACK = `https://cdn.jsdelivr.net/gh/${REPO}@${BRANCH}/output/`;
const SITE = "https://sakazxc1400-creator.github.io/free-vpn-sub/";

// Отдаём только эти файлы: воркер не должен превращаться в открытый прокси.
const ALLOWED = new Set([
  "sub.txt",
  "sub-full.txt",
  "sub-stable.txt",
  "all.txt",
  "all-full.txt",
  "all-stable.txt",
  "stats.json",
  "nodes.json",
  "history.json",
  "clash.yaml",
  "vless.txt",
  "vmess.txt",
  "trojan.txt",
  "ss.txt",
  "hysteria2.txt",
  "tuic.txt",
]);

const ALLOWED_PREFIXES = ["by-country/"];
const BY_COUNTRY = /^by-country\/[a-z]{2}\.txt$/;

function isAllowed(path) {
  if (ALLOWED.has(path)) return true;
  if (ALLOWED_PREFIXES.some((prefix) => path.startsWith(prefix))) {
    return BY_COUNTRY.test(path);
  }
  return false;
}

function contentType(path) {
  if (path.endsWith(".json")) return "application/json; charset=utf-8";
  if (path.endsWith(".yaml")) return "text/yaml; charset=utf-8";
  return "text/plain; charset=utf-8";
}

function corsHeaders() {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET, HEAD, OPTIONS",
    "access-control-max-age": "86400",
  };
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Только GET\n", { status: 405, headers: corsHeaders() });
    }

    const path = url.pathname.replace(/^\/+/, "");
    if (!path) {
      return Response.redirect(SITE, 302);
    }
    if (!isAllowed(path)) {
      return new Response(
        "Такого файла здесь нет. Список файлов: " + SITE + "\n",
        { status: 404, headers: { ...corsHeaders(), "content-type": "text/plain; charset=utf-8" } },
      );
    }

    // Кэш Cloudflare: свой, чтобы не дёргать GitHub на каждый запрос клиента.
    const cache = caches.default;
    const cacheKey = new Request(`https://free-vpn-sub.mirror/${path}`, { method: "GET" });
    const cached = await cache.match(cacheKey);
    if (cached) {
      return new Response(cached.body, { status: 200, headers: { ...corsHeaders(), ...Object.fromEntries(cached.headers) } });
    }

    for (const base of [UPSTREAM, FALLBACK]) {
      let upstream;
      try {
        upstream = await fetch(base + path, {
          headers: { "user-agent": "free-vpn-sub-mirror" },
          cf: { cacheTtl: 300, cacheEverything: true },
        });
      } catch (err) {
        continue;
      }
      if (!upstream.ok) continue;

      const body = await upstream.text();
      const response = new Response(body, {
        status: 200,
        headers: {
          "content-type": contentType(path),
          "cache-control": "public, max-age=300",
          "x-mirror": base === UPSTREAM ? "github" : "jsdelivr",
          ...corsHeaders(),
        },
      });
      ctx.waitUntil(cache.put(cacheKey, response.clone()));
      return response;
    }

    return new Response("Не удалось получить файл ни с GitHub, ни с jsdelivr\n", {
      status: 502,
      headers: { ...corsHeaders(), "content-type": "text/plain; charset=utf-8" },
    });
  },
};
