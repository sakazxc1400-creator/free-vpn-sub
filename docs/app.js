/* Free VPN Sub — логика сайта.
   Данные берутся из ветки data: сначала raw.githubusercontent, если он
   недоступен, переключаемся на зеркало jsdelivr. Ветка плоская: в ней
   лежит только свежий снимок подписок, поэтому она не растёт.

   Всё считается в браузере: ни выбранные узлы, ни своя подписка никуда
   не отправляются. */

(() => {
  "use strict";

  const REPO = "sakazxc1400-creator/free-vpn-sub";
  const BRANCH = "data";
  const RAW = `https://raw.githubusercontent.com/${REPO}/${BRANCH}/output/`;
  const CDN = `https://cdn.jsdelivr.net/gh/${REPO}@${BRANCH}/output/`;
  const GITHUB = `https://github.com/${REPO}`;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- языки ---------- */

  const TEXTS = {
    nav_nodes: { ru: "Узлы", en: "Nodes" },
    nav_stats: { ru: "Статистика", en: "Stats" },
    nav_connect: { ru: "Подключение", en: "Setup" },
    nav_links: { ru: "Ссылки", en: "Links" },
    nav_check: { ru: "Проверка", en: "Check" },
    hero_h1: { ru: "Свободные <span class=\"nowrap\">VPN-узлы</span>, живые прямо сейчас", en: "Free <span class=\"nowrap\">VPN nodes</span> that answer right now" },
    hero_lead: {
      ru: "Каждый час собираю конфиги из открытых источников и прогоняю через sing-box. Оставляю только те серверы, через которые реально идёт трафик, проверяю сертификаты и меряю скорость.",
      en: "Every hour I collect configs from open sources and test them through sing-box. Only servers that actually pass traffic stay, and each one gets a certificate check and a speed measurement.",
    },
    copy_sub: { ru: "Скопировать подписку", en: "Copy subscription" },
    how_to_connect: { ru: "Как подключиться", en: "How to connect" },
    open_clash: { ru: "Clash-конфиг", en: "Clash config" },
    deep_hint: { ru: "Или открой подписку сразу в клиенте:", en: "Or open the subscription straight in a client:" },
    loading: { ru: "Загружаю состояние…", en: "Loading state…" },
    stat_servers: { ru: "серверов", en: "servers" },
    stat_stable: { ru: "стабильных", en: "stable" },
    stat_countries: { ru: "стран", en: "countries" },
    stat_best_ms: { ru: "лучшая задержка", en: "best latency" },
    status_loaded: { ru: "Подписка обновлена, источник {src}", en: "Subscription updated, source {src}" },
    status_failed: { ru: "Не удалось загрузить данные", en: "Could not load data" },
    updated: { ru: "обновление: {when}", en: "updated: {when}" },

    nodes_h2: { ru: "Проверенные узлы", en: "Checked nodes" },
    nodes_p: {
      ru: "Каждый узел прошёл проверку живым трафиком. «Живёт» — сколько часов подряд сервер отвечает в наших прогонах.",
      en: "Every node passed a live traffic test. “Uptime” is how many hours in a row the server keeps answering.",
    },
    all_chip: { ru: "Все", en: "All" },
    only_stable: { ru: "Только стабильные", en: "Stable only" },
    sort_by: { ru: "Сортировка", en: "Sort" },
    sort_rank: { ru: "По качеству", en: "Best overall" },
    sort_speed: { ru: "По скорости", en: "By speed" },
    sort_latency: { ru: "По задержке", en: "By latency" },
    sort_uptime: { ru: "По сроку жизни", en: "By uptime" },
    search_ph: { ru: "Страна или адрес", en: "Country or address" },
    col_server: { ru: "Сервер", en: "Server" },
    col_proto: { ru: "Протокол", en: "Protocol" },
    col_speed: { ru: "Скорость", en: "Speed" },
    col_latency: { ru: "Задержка", en: "Latency" },
    col_uptime: { ru: "Живёт", en: "Uptime" },
    col_addr: { ru: "Адрес", en: "Address" },
    more: { ru: "Показать ещё", en: "Show more" },
    board_loading: { ru: "Загружаю список…", en: "Loading list…" },
    board_shown: { ru: "Показано {n} из {m} узлов подписки", en: "Showing {n} of {m} nodes" },
    uptime_new: { ru: "новый", en: "new" },
    stable_pending: { ru: "пока копится", en: "still filling" },
    check_stable_empty: { ru: "0 · узлы должны прожить 6 прогонов подряд", en: "0 · nodes must survive 6 runs in a row" },
    board_empty: { ru: "Ничего не найдено, сбрось фильтр", en: "Nothing matches, reset the filters" },
    board_failed: { ru: "Не удалось загрузить список. Проверь ссылку на подписку вручную.", en: "Could not load the list. Check the subscription link manually." },
    warn_title: { ru: "Сертификат не проверился: узел может подменять TLS", en: "Certificate check failed: this node may intercept TLS" },

    builder_h2: { ru: "Своя подписка", en: "Your own subscription" },
    builder_none: { ru: "ничего не выбрано", en: "nothing selected" },
    builder_n_selected: { ru: "выбрано: {n}", en: "selected: {n}" },
    builder_hint: {
      ru: "Отметь галочками узлы в списке выше и забери только их. Файл собирается в браузере, никуда не отправляется.",
      en: "Tick nodes in the list above and take only those. The file is built in your browser and never sent anywhere.",
    },
    builder_download: { ru: "Скачать файл", en: "Download file" },
    builder_copy: { ru: "Скопировать base64", en: "Copy base64" },
    builder_copy_plain: { ru: "Скопировать ссылки", en: "Copy links" },
    builder_best: { ru: "Выбрать 10 лучших", en: "Pick top 10" },
    builder_clear: { ru: "Сбросить выбор", en: "Clear selection" },
    builder_empty: { ru: "Сначала отметь узлы", en: "Select nodes first" },

    stats_h2: { ru: "Что внутри", en: "What is inside" },
    stats_p: { ru: "Числа последнего прогона и раскладка по протоколам и странам.", en: "Numbers from the last run, split by protocol and country." },
    card_unique: { ru: "уникальных кандидатов", en: "unique candidates" },
    card_tcp: { ru: "прошли TCP-проверку", en: "passed TCP check" },
    card_verified: { ru: "реально работают", en: "really work" },
    card_servers: { ru: "уникальных адресов", en: "unique addresses" },
    card_tls: { ru: "с проверенным сертификатом", en: "certificate verified" },
    card_stable: { ru: "живут несколько часов", en: "alive for hours" },
    card_speed: { ru: "лучшая скорость, Мбит/с", en: "top speed, Mbps" },
    card_speed_med: { ru: "медиана скорости, Мбит/с", en: "median speed, Mbps" },
    panel_proto: { ru: "Протоколы", en: "Protocols" },
    panel_country: { ru: "Страны", en: "Countries" },

    connect_h2: { ru: "Как подключиться", en: "How to connect" },
    connect_p: { ru: "Выбери систему, вставь ссылку в клиент и обнови подписку.", en: "Pick your system, paste the link into a client and refresh." },

    links_h2: { ru: "Ссылки на подписку", en: "Subscription links" },
    links_p: {
      ru: "Основная грузится быстрее, стабильная держится часами, полная выручает, если в основной ничего не подключается.",
      en: "The main one loads faster, the stable one keeps servers for hours, the full one helps when nothing in the main list connects.",
    },
    card_main: { ru: "Основная", en: "Main" },
    tag_main: { ru: "отобраны по скорости", en: "picked by speed" },
    card_stable_sub: { ru: "Стабильная", en: "Stable" },
    tag_stable: { ru: "живут часами", en: "alive for hours" },
    card_full: { ru: "Полная", en: "Full" },
    tag_full: { ru: "все рабочие", en: "all working" },
    tag_clash: { ru: "формат yaml", en: "yaml format" },
    copy: { ru: "Скопировать", en: "Copy" },
    qr: { ru: "QR-код", en: "QR code" },
    hide_qr: { ru: "Скрыть QR", en: "Hide QR" },
    open_txt: { ru: "Открыть txt", en: "Open txt" },
    copied: { ru: "Скопировано", en: "Copied" },
    copy_failed: { ru: "Не вышло", en: "Failed" },
    mirrors_p: { ru: "Если raw.githubusercontent.com не открывается, есть зеркала. Содержимое то же.", en: "If raw.githubusercontent.com is blocked, use a mirror. The content is the same." },
    mirror_copy: { ru: "Копировать", en: "Copy" },

    check_h2: { ru: "Проверка подписки", en: "Subscription check" },
    check_p: {
      ru: "Проверяет доступность ссылок и свежесть списка из браузера. Отдельные серверы так проверить нельзя: для этого в клиенте есть тест задержки.",
      en: "Checks that the links are reachable and the list is fresh, right from your browser. Individual servers cannot be tested this way: use the latency test in your client.",
    },
    check_btn: { ru: "Проверить сейчас", en: "Check now" },
    check_running: { ru: "Проверяю…", en: "Checking…" },
    check_idle: { ru: "Ещё не запускалось.", en: "Not started yet." },
    check_source: { ru: "источник данных", en: "data source" },
    check_stats: { ru: "stats.json загружен", en: "stats.json loaded" },
    check_updated: { ru: "список обновлён", en: "list updated" },
    check_count: { ru: "серверов в подписке", en: "servers in the subscription" },
    check_stable: { ru: "из них стабильных", en: "of them stable" },
    check_fresh: { ru: "свежесть", en: "freshness" },
    check_fresh_ok: { ru: "свежий", en: "fresh" },
    check_fresh_bad: { ru: "давно не обновлялся", en: "stale" },
    check_nodes: { ru: "nodes.json", en: "nodes.json" },
    check_stable_link: { ru: "ссылка на стабильную", en: "stable subscription link" },
    check_clash: { ru: "clash.yaml", en: "clash.yaml" },
    check_bad: { ru: "недоступен ни на raw, ни на jsdelivr", en: "unavailable on raw and jsdelivr" },
    check_size: { ru: "размер списка", en: "list size" },
    check_speed: { ru: "скорость загрузки", en: "download speed" },
    check_ok: { ru: "ок", en: "ok" },
    check_rows: { ru: "узлов в списке", en: "nodes in the list" },

    safety_h2: { ru: "Про безопасность", en: "About safety" },
    safety_lead: { ru: "Прочитай перед использованием.", en: "Read this before using." },
    safety: {
      ru: [
        "Владелец сервера может видеть твой трафик. Эти серверы запускают неизвестные люди, и я не знаю, как они с ним обращаются. Оператор может узнать, какие сайты ты посещаешь.",
        "Поэтому каждый узел дополнительно проверяется HTTPS-запросом с полной проверкой сертификата. Узел, который подменяет сертификаты и читает содержимое соединений, в основную подписку не попадает: в полной он помечен знаком ⚠.",
        "Не используй такие серверы для банковских приложений, госуслуг, рабочей почты и важных аккаунтов. Не передавай через них пароли, документы и платёжные данные.",
        "Подписка нужна для обхода блокировок, а не для полной анонимности. Если нужна приватность, бери платный сервис или поднимай свой сервер: VLESS+Reality на недорогом VPS работает быстрее бесплатных узлов.",
      ],
      en: [
        "The server owner can see your traffic. These servers are run by strangers and I have no idea what they do with it. Your ISP can also learn which sites you visit.",
        "That is why every node additionally passes an HTTPS request with full certificate validation. A node that intercepts certificates to read connection contents never gets into the main subscription: in the full list it is marked with ⚠.",
        "Do not use these servers for banking apps, government services, work mail or important accounts. Never send passwords, documents or payment data through them.",
        "This subscription is for bypassing blocks, not for real anonymity. If you need privacy, buy a paid service or run your own server: VLESS+Reality on a cheap VPS is faster than free nodes.",
      ],
    },

    support_h2: { ru: "Поддержать проект", en: "Support the project" },
    support_p: { ru: "Подписка была и остаётся бесплатной. Если пригодилась, можно помочь.", en: "The subscription is and stays free. If it helped, you can give back." },
    donate: { ru: "Донат", en: "Donate" },
    star_hint: { ru: "Самый простой способ помочь без денег: поставить звезду репозиторию.", en: "The easiest way to help for free: star the repository." },
    open_github: { ru: "Открыть на GitHub", en: "Open on GitHub" },
    copy_addr: { ru: "Скопировать адрес", en: "Copy address" },
    foot_note: {
      ru: "Free VPN Sub · MIT · репозиторий собирает публичные конфиги в один список и не предоставляет VPN-услуги. Серверы принадлежат третьим лицам.",
      en: "Free VPN Sub · MIT · the repository collects public configs into one list and does not provide VPN services. The servers belong to third parties.",
    },
    hours_short: { ru: "ч", en: "h" },
    deep_open: { ru: "Открыть в {name}", en: "Open in {name}" },
  };

  let lang = document.documentElement.lang === "en" ? "en" : "ru";

  function t(key) {
    const row = TEXTS[key];
    if (!row) return key;
    return row[lang] || row.ru || key;
  }

  function tf(key, vars) {
    return t(key).replace(/\{(\w+)\}/g, (m, name) => (vars && name in vars ? vars[name] : m));
  }

  /* ---------- платформы ---------- */

  const PLATFORMS = {
    windows: {
      title: "Windows",
      ru: {
        steps: [
          "Скачай <a href=\"https://github.com/MatsuriDayo/nekoray/releases\" target=\"_blank\" rel=\"noopener\">Nekoray</a>, архив <code>nekoray-*-windows64.zip</code>, и распакуй его.",
          "В настройках выбери ядро <strong>sing-box</strong>.",
          "Добавь профиль из подписки и вставь ссылку.",
          "Обнови подписки, выбери сервер сверху списка и нажми <kbd>Enter</kbd>.",
          "Нажми <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>S</kbd>, чтобы включить системный прокси.",
        ],
        hint: "Вместо Nekoray можно взять v2rayN, ссылка добавляется в разделе «Подписки».",
      },
      en: {
        steps: [
          "Download <a href=\"https://github.com/MatsuriDayo/nekoray/releases\" target=\"_blank\" rel=\"noopener\">Nekoray</a>, the <code>nekoray-*-windows64.zip</code> archive, and unpack it.",
          "In settings pick the <strong>sing-box</strong> core.",
          "Add a profile from subscription and paste the link.",
          "Refresh subscriptions, pick a server near the top and press <kbd>Enter</kbd>.",
          "Press <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>S</kbd> to enable the system proxy.",
        ],
        hint: "v2rayN works too: the link goes into its “Subscriptions” section.",
      },
      links: [["Nekoray", "https://github.com/MatsuriDayo/nekoray/releases"], ["v2rayN", "https://github.com/2dust/v2rayN/releases"]],
    },
    android: {
      title: "Android",
      ru: {
        steps: [
          "Установи v2rayNG или Hiddify.",
          "Открой настройки групп подписок и нажми <kbd>+</kbd>.",
          "Вставь ссылку и сохрани.",
          "Обнови подписки, выбери сервер и подключись.",
        ],
        hint: "Для Hysteria2 и TUIC удобнее Hiddify. Подписка добавляется через «+» и «Добавить из ссылки».",
      },
      en: {
        steps: [
          "Install v2rayNG or Hiddify.",
          "Open subscription group settings and tap <kbd>+</kbd>.",
          "Paste the link and save.",
          "Refresh subscriptions, pick a server and connect.",
        ],
        hint: "Hiddify handles Hysteria2 and TUIC better. Add the subscription via “+” and “Add from link”.",
      },
      links: [["v2rayNG", "https://github.com/2dust/v2rayNG/releases"], ["Hiddify", "https://github.com/hiddify/hiddify-next/releases"]],
    },
    ios: {
      title: "iPhone",
      ru: {
        steps: [
          "Поставь Streisand, v2Box или Shadowrocket. Первые два бесплатные.",
          "Открой раздел подписок и нажми <kbd>+</kbd>.",
          "Вставь ссылку и обнови список.",
          "Выбери сервер и подключись.",
        ],
        hint: "Shadowrocket платный, но стабильнее остальных. Умеет импорт по ссылке sing-box://.",
      },
      en: {
        steps: [
          "Install Streisand, v2Box or Shadowrocket. The first two are free.",
          "Open the subscriptions section and tap <kbd>+</kbd>.",
          "Paste the link and refresh the list.",
          "Pick a server and connect.",
        ],
        hint: "Shadowrocket is paid but the most reliable, and it can import sing-box:// links.",
      },
      links: [],
    },
    macos: {
      title: "macOS",
      ru: {
        steps: [
          "Возьми Hiddify или V2RayXS.",
          "Добавь подписку по ссылке.",
          "Обнови список и подключись к серверу.",
        ],
        hint: "Hiddify ставится из dmg, V2RayXS через Homebrew. Есть и sing-box для macOS.",
      },
      en: {
        steps: [
          "Take Hiddify or V2RayXS.",
          "Add the subscription by link.",
          "Refresh the list and connect.",
        ],
        hint: "Hiddify ships as a dmg, V2RayXS installs through Homebrew. sing-box for macOS works too.",
      },
      links: [["Hiddify", "https://github.com/hiddify/hiddify-next/releases"], ["sing-box", "https://github.com/SagerNet/sing-box/releases"]],
    },
    linux: {
      title: "Linux",
      ru: {
        steps: [
          "Скачай Nekoray или Hiddify в формате AppImage.",
          "Дай файлу право на запуск: <code>chmod +x имя.AppImage</code>.",
          "Добавь подписку, обнови список и выбери сервер.",
        ],
        hint: "Nekoray использует ядро sing-box, Hiddify удобнее для Hysteria2 и TUIC.",
      },
      en: {
        steps: [
          "Download Nekoray or Hiddify as an AppImage.",
          "Make it executable: <code>chmod +x name.AppImage</code>.",
          "Add the subscription, refresh and pick a server.",
        ],
        hint: "Nekoray runs the sing-box core, Hiddify is nicer for Hysteria2 and TUIC.",
      },
      links: [["Nekoray", "https://github.com/MatsuriDayo/nekoray/releases"], ["Hiddify", "https://github.com/hiddify/hiddify-next/releases"]],
    },
  };

  /* ---------- утилиты ---------- */

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function setNum(el, value) {
    if (value === null || value === undefined || Number.isNaN(value)) { el.textContent = "—"; return; }
    el.textContent = String(value);
  }

  function animateNum(el, target, suffix = "") {
    if (!Number.isFinite(target)) { setNum(el, target); return; }
    const final = target.toLocaleString(lang === "ru" ? "ru-RU" : "en-US") + suffix;
    // Правильное число ставим сразу. Анимация — только украшение: если
    // вкладка в фоне и кадров нет, цифра всё равно останется верной.
    el.textContent = final;
    if (reduceMotion) return;
    const dur = 900;
    const t0 = performance.now();
    let done = false;
    // У небольших чисел вроде скорости 1.8 показываем десятые: иначе
    // счёт выглядит как 0, 1, 2 и сбивает с толку.
    const decimals = Math.abs(target) < 10 && !Number.isInteger(target) ? 1 : 0;
    const fmt = (v) => v.toLocaleString(lang === "ru" ? "ru-RU" : "en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }) + suffix;
    const finish = () => { if (!done) { done = true; el.textContent = final; } };
    const step = (now) => {
      if (done) return;
      const p = Math.min(1, (now - t0) / dur);
      if (p >= 1) { done = true; el.textContent = final; return; }
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(target * eased);
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
    setTimeout(finish, dur + 150);
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
      ta.remove();
      return ok;
    }
  }

  function flashNote(el, message, bad = false) {
    if (!el) return;
    el.textContent = message;
    el.style.color = bad ? "var(--danger)" : "var(--teal)";
    clearTimeout(el._timer);
    el._timer = setTimeout(() => { el.textContent = ""; }, 3200);
  }

  function download(name, text) {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  }

  function toBase64(text) {
    // btoa не умеет юникод, а в названиях узлов есть флаги и кириллица.
    const bytes = new TextEncoder().encode(text);
    let binary = "";
    for (const b of bytes) binary += String.fromCharCode(b);
    return btoa(binary);
  }

  /* ---------- сеть ---------- */

  const state = { source: "raw" };

  async function fetchText(name, timeout = 9000) {
    const started = performance.now();
    for (const base of [RAW, CDN]) {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), timeout);
      try {
        const resp = await fetch(base + name, { cache: "no-store", signal: ctrl.signal });
        clearTimeout(timer);
        if (resp.ok) {
          const text = await resp.text();
          state.source = base === RAW ? "raw" : "jsdelivr";
          return { text, ms: Math.round(performance.now() - started), source: state.source };
        }
      } catch (err) {
        clearTimeout(timer);
      }
    }
    return null;
  }

  /* ---------- тема ---------- */

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("fvps-theme", theme); } catch (e) {}
    const meta = $("#theme-color");
    if (meta) meta.setAttribute("content", theme === "light" ? "#f6f7fb" : "#0a0e16");
  }

  /* ---------- фон: дрейфующая сеть ---------- */

  const NET_PALETTE = {
    dark: { line: "120, 150, 200", alpha: 0.16, dot: "244, 185, 66" },
    light: { line: "86, 106, 150", alpha: 0.13, dot: "184, 121, 26" },
  };

  function initNet() {
    const canvas = $("#net");
    if (!canvas || reduceMotion) return;
    const ctx = canvas.getContext("2d");
    let w = 0, h = 0, nodes = [], dpr = 1;

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.max(26, Math.min(64, Math.round((w * h) / 26000)));
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        r: 1 + Math.random() * 1.6,
      }));
    };

    const linkDist = 148;

    function frame() {
      const palette = NET_PALETTE[document.documentElement.dataset.theme] || NET_PALETTE.dark;
      ctx.clearRect(0, 0, w, h);
      for (const n of nodes) {
        n.x += n.vx; n.y += n.vy;
        if (n.x < 0 || n.x > w) n.vx *= -1;
        if (n.y < 0 || n.y > h) n.vy *= -1;
      }
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const d = Math.hypot(dx, dy);
          if (d < linkDist) {
            const a = (1 - d / linkDist) * palette.alpha;
            ctx.strokeStyle = `rgba(${palette.line}, ${a})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.stroke();
          }
        }
      }
      for (const n of nodes) {
        ctx.fillStyle = `rgba(${palette.dot}, 0.5)`;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fill();
      }
      requestAnimationFrame(frame);
    }

    resize();
    window.addEventListener("resize", resize);
    requestAnimationFrame(frame);
  }

  /* ---------- статистика ---------- */

  function renderBars(container, entries, opts) {
    if (!container) return;
    container.innerHTML = "";
    const max = Math.max(1, ...entries.map((e) => e[1]));
    for (const [label, value] of entries) {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.className = "bar-label";
      name.textContent = opts.format ? opts.format(label) : label;
      const track = document.createElement("span");
      track.className = "bar-track";
      const fill = document.createElement("i");
      fill.className = "bar-fill";
      track.appendChild(fill);
      const val = document.createElement("span");
      val.className = "bar-val";
      val.textContent = value;
      li.append(name, track, val);
      container.appendChild(li);
      const pct = Math.max(4, Math.round((value / max) * 100));
      // Полоска анимируется CSS-переходом. Ширину ставим сразу после
      // вставки в документ: в фоновой вкладке кадров нет, а полоска
      // всё равно должна оказаться правильной.
      fill.style.width = "0%";
      void fill.offsetWidth;
      fill.style.width = pct + "%";
    }
  }

  const FLAGS = {
    US: "🇺🇸", NL: "🇳🇱", DE: "🇩🇪", HK: "🇭🇰", KR: "🇰🇷", JP: "🇯🇵", SG: "🇸🇬",
    CA: "🇨🇦", FR: "🇫🇷", GB: "🇬🇧", RU: "🇷🇺", BR: "🇧🇷", FI: "🇫🇮", PL: "🇵🇱",
    SE: "🇸🇪", CH: "🇨🇭", IN: "🇮🇳", RO: "🇷🇴", TR: "🇹🇷", IT: "🇮🇹", ES: "🇪🇸",
    TW: "🇹🇼", AU: "🇦🇺", AT: "🇦🇹", LV: "🇱🇻", HU: "🇭🇺", EE: "🇪🇪", BG: "🇧🇬",
    MY: "🇲🇾", SC: "🇸🇨", ZA: "🇿🇦", AE: "🇦🇪", KZ: "🇰🇿", NO: "🇳🇴", DK: "🇩🇰",
    CZ: "🇨🇿", LT: "🇱🇹", MX: "🇲🇽", TH: "🇹🇭", VN: "🇻🇳", ID: "🇮🇩", UA: "🇺🇦",
    MD: "🇲🇩", BY: "🇧🇾", GE: "🇬🇪", AL: "🇦🇱", CY: "🇨🇾", CR: "🇨🇷", CL: "🇨🇱",
  };

  function flagOf(code) {
    if (!code || code === "XX") return "🏴";
    if (FLAGS[code]) return FLAGS[code];
    if (code.length !== 2) return "🏴";
    return String.fromCodePoint(...[...code.toUpperCase()].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
  }

  let lastStats = null;

  // Когда стабильных узлов ещё нет (первые часы после запуска), карточка
  // стабильной подписки честно говорит, что список копится.
  function applyStableTag(data) {
    const anchor = document.querySelector("#url-stable");
    const tag = anchor ? anchor.closest(".link-card").querySelector(".tag-live") : null;
    if (!tag || !data || typeof data.stable !== "number") return;
    const pending = data.stable === 0;
    tag.textContent = pending ? t("stable_pending") : t("tag_stable");
    tag.classList.toggle("is-wait", pending);
  }

  function renderStatsNumbers(data) {
    $$("[data-num]").forEach((el) => {
      const key = el.dataset.num;
      const value = data[key];
      if (typeof value === "number") {
        animateNum(el, value);
      } else {
        setNum(el, value);
        // Карточку со статистикой, которой ещё нет в stats.json,
        // показывать нечего: старые сборки её просто не содержат.
        const card = el.closest(".stat-card");
        if (card && (value === undefined || value === null)) card.hidden = true;
      }
    });
  }

  async function loadStats() {
    const res = await fetchText("stats.json");
    if (!res) {
      const status = $("#live-status");
      if (status) status.textContent = t("status_failed");
      return null;
    }
    let data;
    try { data = JSON.parse(res.text); } catch (e) { return null; }

    lastStats = data;
    renderStatsNumbers(data);
    applyStableTag(data);

    const status = $("#live-status");
    if (status) status.textContent = tf("status_loaded", { src: res.source });

    const upd = $("#live-updated");
    if (upd && data.updated) upd.textContent = tf("updated", { when: data.updated });

    const protos = Object.entries(data.by_protocol || {}).sort((a, b) => b[1] - a[1]);
    renderBars($("#proto-bars"), protos, { format: (p) => p });

    const countries = Object.entries(data.by_country || {}).slice(0, 12);
    renderBars($("#country-bars"), countries, { format: (c) => `${flagOf(c)} ${c}` });

    return data;
  }

  /* ---------- разбор строки подписки (запасной путь) ---------- */

  function hostOf(base) {
    if (base.startsWith("vmess://")) {
      try {
        const json = JSON.parse(atob(base.slice(8)));
        return `${json.add || "?"}:${json.port || "?"}`;
      } catch (e) { return "vmess"; }
    }
    const after = base.replace(/^[a-z0-9]+:\/\//i, "").split(/[?#]/)[0];
    const hostport = after.split("@").pop() || "";
    return hostport.replace(/\/.*$/, "");
  }

  function parseLine(line) {
    const hash = line.indexOf("#");
    if (hash < 0) return null;
    const url = line.trim();
    const base = line.slice(0, hash).trim();
    let tag;
    try { tag = decodeURIComponent(line.slice(hash + 1)); } catch (e) { tag = line.slice(hash + 1); }
    const parts = tag.split(" · ");
    if (parts.length < 2) return null;

    const head = parts[0].replace(/^\d+\.\s*/, "");
    const tokens = head.split(" ");
    const flag = tokens[0] || "🏴";
    const country = tokens.slice(1).join(" ") || "—";
    const proto = parts[1];
    const ms = parts[2] ? parseInt(parts[2], 10) : null;

    let up = null;
    for (const part of parts.slice(3)) {
      const found = /^(\d+)\s*[чh]$/.exec(part.trim());
      if (found) up = Number(found[1]);
    }

    return {
      url,
      base,
      cc: "",
      flag,
      name: country,
      proto,
      ms: Number.isFinite(ms) ? ms : null,
      mbps: null,
      up,
      tls: tag.indexOf("⚠") < 0,
      addr: hostOf(base),
    };
  }

  /* ---------- доска узлов ---------- */

  const board = {
    rows: [],
    proto: "",
    query: "",
    limit: 18,
    onlyStable: false,
    sort: "rank",
    picked: new Set(),
  };

  const STABLE_HOURS = 3;

  function sortRows(rows) {
    const byRank = (a, b) => {
      if (a.tls !== b.tls) return a.tls ? -1 : 1;
      const aSpeed = a.mbps === null || a.mbps === undefined ? -1 : a.mbps;
      const bSpeed = b.mbps === null || b.mbps === undefined ? -1 : b.mbps;
      if (aSpeed !== bSpeed) return bSpeed - aSpeed;
      return (a.ms === null ? 1e9 : a.ms) - (b.ms === null ? 1e9 : b.ms);
    };
    const copy = rows.slice();
    if (board.sort === "speed") {
      copy.sort((a, b) => {
        const aSpeed = a.mbps === null || a.mbps === undefined ? -1 : a.mbps;
        const bSpeed = b.mbps === null || b.mbps === undefined ? -1 : b.mbps;
        if (aSpeed !== bSpeed) return bSpeed - aSpeed;
        return (a.ms === null ? 1e9 : a.ms) - (b.ms === null ? 1e9 : b.ms);
      });
    } else if (board.sort === "latency") {
      copy.sort((a, b) => (a.ms === null ? 1e9 : a.ms) - (b.ms === null ? 1e9 : b.ms));
    } else if (board.sort === "uptime") {
      copy.sort((a, b) => (b.up || 0) - (a.up || 0) || byRank(a, b));
    } else {
      copy.sort(byRank);
    }
    return copy;
  }

  function filtered() {
    const q = board.query.trim().toLowerCase();
    const rows = board.rows.filter((r) => {
      if (board.proto && r.proto !== board.proto) return false;
      if (board.onlyStable && (r.up || 0) < STABLE_HOURS) return false;
      if (q) {
        const hay = `${r.name} ${r.addr} ${r.proto} ${r.cc}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    return sortRows(rows);
  }

  function renderChips() {
    const counts = new Map();
    for (const r of board.rows) counts.set(r.proto, (counts.get(r.proto) || 0) + 1);
    const container = $("#proto-chips");
    if (!container) return;
    container.innerHTML = "";
    const make = (label, value) => {
      const b = document.createElement("button");
      b.className = "chip" + (board.proto === value ? " is-active" : "");
      b.dataset.proto = value;
      b.textContent = label;
      b.addEventListener("click", () => {
        board.proto = value;
        board.limit = 18;
        renderChips();
        renderRows();
      });
      container.appendChild(b);
    };
    make(`${t("all_chip")} · ${board.rows.length}`, "");
    for (const [proto, n] of [...counts.entries()].sort((a, b) => b[1] - a[1])) {
      make(`${proto} · ${n}`, proto);
    }
  }

  function renderRows() {
    const rows = filtered();
    const shown = rows.slice(0, board.limit);
    const msValues = rows.map((r) => r.ms).filter((v) => Number.isFinite(v));
    const minMs = Math.min(...msValues, 0);
    const maxMs = Math.max(...msValues, 1);

    const ol = $("#board-rows");
    ol.innerHTML = "";
    const frag = document.createDocumentFragment();

    shown.forEach((r, i) => {
      const li = document.createElement("li");
      li.tabIndex = 0;
      li.style.animationDelay = reduceMotion ? "0s" : `${(i % 30) * 16}ms`;
      if (!r.tls) li.classList.add("is-warn");

      const pick = document.createElement("label");
      pick.className = "pick";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = board.picked.has(r.addr);
      box.setAttribute("aria-label", `${t("col_server")} ${r.addr}`);
      box.addEventListener("change", () => {
        if (box.checked) board.picked.add(r.addr);
        else board.picked.delete(r.addr);
        updateBuilder();
      });
      pick.appendChild(box);

      const idx = document.createElement("span");
      idx.className = "idx";
      idx.textContent = String(r.i).padStart(2, "0");

      const who = document.createElement("span");
      who.className = "who";
      const flag = document.createElement("span");
      flag.className = "flag";
      flag.textContent = r.flag;
      const cname = document.createElement("span");
      cname.className = "cname";
      cname.textContent = r.name;
      who.append(flag, cname);
      if (!r.tls) {
        const warn = document.createElement("span");
        warn.className = "warn-mark";
        warn.textContent = "⚠";
        warn.title = t("warn_title");
        who.appendChild(warn);
      }

      const proto = document.createElement("span");
      proto.className = "proto";
      proto.textContent = r.proto;

      const speed = document.createElement("span");
      speed.className = "speed";
      if (r.mbps === null || r.mbps === undefined) {
        speed.textContent = "—";
      } else {
        speed.textContent = `${r.mbps}M`;
        speed.title = lang === "ru" ? `${r.mbps} Мбит/с` : `${r.mbps} Mbps`;
      }

      const lat = document.createElement("span");
      lat.className = "lat";
      const num = document.createElement("span");
      num.className = "lat-num";
      num.textContent = r.ms === null ? "—" : `${r.ms}ms`;
      const meter = document.createElement("span");
      meter.className = "meter";
      const fill = document.createElement("i");
      if (r.ms !== null && maxMs > minMs) {
        const speedPct = (maxMs - r.ms) / (maxMs - minMs);
        fill.style.width = `${Math.round(6 + speedPct * 94)}%`;
      } else {
        fill.style.width = "30%";
      }
      meter.appendChild(fill);
      lat.append(num, meter);

      const uptime = document.createElement("span");
      uptime.className = "uptime";
      if (!r.up) uptime.textContent = "—";
      else if (r.up < 1) { uptime.textContent = t("uptime_new"); uptime.classList.add("is-new"); }
      else uptime.textContent = `${Math.round(r.up)}${t("hours_short")}`;

      const addr = document.createElement("span");
      addr.className = "addr";
      addr.textContent = r.addr;

      li.append(pick, idx, who, proto, speed, lat, uptime, addr);
      frag.appendChild(li);
    });

    ol.appendChild(frag);

    // В фоновой вкладке CSS-анимация может заморозиться и строки остались бы
    // прозрачными, поэтому через паузу принудительно показываем их.
    setTimeout(() => {
      ol.querySelectorAll("li").forEach((li) => {
        li.style.opacity = "1";
        li.style.transform = "none";
      });
    }, 1500);

    $("#more-btn").hidden = shown.length >= rows.length;
    const note = $("#board-note");
    note.textContent = rows.length
      ? tf("board_shown", { n: shown.length, m: rows.length })
      : t("board_empty");
  }

  function loadBoardFallback(text) {
    return text
      .split("\n")
      .map(parseLine)
      .filter(Boolean)
      .map((r, i) => ({ ...r, i: i + 1 }));
  }

  async function loadNodes() {
    const note = $("#board-note");
    // Основной источник: nodes.json из последнего прогона. Он несёт больше
    // полей, чем разбор названий, и ссылки на сами узлы.
    const structured = await fetchText("nodes.json", 12000);
    if (structured) {
      try {
        const data = JSON.parse(structured.text);
        if (Array.isArray(data) && data.length) {
          board.rows = data.map((n, i) => ({
            url: n.url || "",
            base: (n.url || "").split("#")[0],
            cc: n.cc || "",
            flag: flagOf(n.cc),
            name: n.name || n.cc || "—",
            proto: n.proto,
            ms: Number.isFinite(n.ms) ? n.ms : null,
            mbps: Number.isFinite(n.mbps) ? n.mbps : null,
            up: Number.isFinite(n.up) ? n.up : null,
            tls: n.tls !== false,
            addr: n.addr,
            i: Number.isFinite(n.i) ? n.i : i + 1,
          }));
          if (board.rows.some((r) => !r.url)) {
            // Сборки до появления поля url: ссылки добираем из all.txt,
            // чтобы «своя подписка» работала и на старых данных.
            const plain = await fetchText("all.txt");
            if (plain) {
              const byAddr = new Map();
              for (const row of loadBoardFallback(plain.text)) byAddr.set(row.addr, row.url);
              for (const row of board.rows) if (!row.url) row.url = byAddr.get(row.addr) || "";
            }
          }
          renderChips();
          renderRows();
          updateBuilder();
          return;
        }
      } catch (e) { /* ниже откатимся на all.txt */ }
    }

    const res = await fetchText("all.txt");
    if (!res) {
      note.textContent = t("board_failed");
      return;
    }
    board.rows = loadBoardFallback(res.text);
    renderChips();
    renderRows();
    updateBuilder();
  }

  /* ---------- своя подписка ---------- */

  function pickedRows() {
    return board.rows.filter((r) => board.picked.has(r.addr) && r.url);
  }

  function updateBuilder() {
    const count = pickedRows().length;
    const label = $("#builder-count");
    if (label) label.textContent = count ? tf("builder_n_selected", { n: count }) : t("builder_none");
  }

  function builderText() {
    return pickedRows().map((r) => r.url).join("\n");
  }

  function initBuilder() {
    $("#builder-download").addEventListener("click", () => {
      const text = builderText();
      if (!text) { flashNote($("#copy-note"), t("builder_empty"), true); return; }
      download("free-vpn-sub.txt", toBase64(text));
      flashNote($("#copy-note"), t("copied"));
    });

    $("#builder-copy").addEventListener("click", async () => {
      const text = builderText();
      if (!text) { flashNote($("#copy-note"), t("builder_empty"), true); return; }
      const ok = await copyText(toBase64(text));
      flashNote($("#copy-note"), ok ? t("copied") : t("copy_failed"), !ok);
    });

    $("#builder-copy-plain").addEventListener("click", async () => {
      const text = builderText();
      if (!text) { flashNote($("#copy-note"), t("builder_empty"), true); return; }
      const ok = await copyText(text);
      flashNote($("#copy-note"), ok ? t("copied") : t("copy_failed"), !ok);
    });

    $("#builder-best").addEventListener("click", () => {
      const best = filtered().filter((r) => r.url).slice(0, 10);
      board.picked = new Set(best.map((r) => r.addr));
      renderRows();
      updateBuilder();
    });

    $("#builder-clear").addEventListener("click", () => {
      board.picked.clear();
      renderRows();
      updateBuilder();
    });
  }

  /* ---------- ссылки, зеркала, deep links ---------- */

  const SUBS = {
    main: RAW + "sub.txt",
    stable: RAW + "sub-stable.txt",
    full: RAW + "sub-full.txt",
    clash: RAW + "clash.yaml",
  };

  // Свои зеркала, например развёрнутый Cloudflare Worker (см. mirror/README.md).
  // Пример: [["cloudflare · основная", "https://имя.аккаунт.workers.dev/sub.txt"]]
  const EXTRA_MIRRORS = [];

  function initLinks() {
    $("#url-main").textContent = SUBS.main;
    $("#url-stable").textContent = SUBS.stable;
    $("#url-full").textContent = SUBS.full;
    $("#url-clash").textContent = SUBS.clash;

    $("#dl-main").href = RAW + "all.txt";
    $("#dl-stable").href = RAW + "all-stable.txt";
    $("#dl-full").href = RAW + "all-full.txt";
    $("#dl-clash").href = RAW + "clash.yaml";

    $("#hero-copy").dataset.copy = SUBS.main;

    const mirrors = [
      ["jsdelivr · основная", CDN + "sub.txt"],
      ["gh-proxy · основная", "https://gh-proxy.com/" + SUBS.main],
      ["raw · основная", SUBS.main],
      ["jsdelivr · стабильная", CDN + "sub-stable.txt"],
      ["raw · стабильная", SUBS.stable],
      ["jsdelivr · полная", CDN + "sub-full.txt"],
      ["gh-proxy · полная", "https://gh-proxy.com/" + SUBS.full],
      ["raw · полная", SUBS.full],
      ["jsdelivr · Clash", CDN + "clash.yaml"],
      ["raw · Clash", SUBS.clash],
      ...EXTRA_MIRRORS,
    ];
    const list = $("#mirror-list");
    list.innerHTML = "";
    for (const [name, url] of mirrors) {
      const row = document.createElement("div");
      row.className = "mirror";
      const label = document.createElement("span");
      label.className = "mirror-name";
      label.textContent = name;
      const code = document.createElement("code");
      code.textContent = url;
      const btn = document.createElement("button");
      btn.className = "ghost-btn small";
      btn.textContent = t("mirror_copy");
      btn.addEventListener("click", async () => {
        const ok = await copyText(url);
        btn.textContent = ok ? t("copied") : t("copy_failed");
        setTimeout(() => { btn.textContent = t("mirror_copy"); }, 1800);
      });
      row.append(label, code, btn);
      list.appendChild(row);
    }
  }

  const DEEP_LINKS = [
    { name: "v2rayNG", href: (url) => `v2rayng://install-sub?url=${encodeURIComponent(url)}#FreeVPNSub` },
    { name: "Hiddify", href: (url) => `hiddify://import/${url}` },
    { name: "sing-box", href: (url) => `sing-box://import-remote-profile?url=${encodeURIComponent(url)}#FreeVPNSub` },
  ];

  function initDeepLinks() {
    const box = $("#deep-links");
    if (!box) return;
    box.innerHTML = "";
    const hint = document.createElement("span");
    hint.className = "deep-hint";
    hint.textContent = t("deep_hint");
    box.appendChild(hint);
    for (const client of DEEP_LINKS) {
      const a = document.createElement("a");
      a.className = "ghost-btn small";
      a.href = client.href(SUBS.main);
      a.textContent = client.name;
      a.title = tf("deep_open", { name: client.name });
      box.appendChild(a);
    }
  }

  /* ---------- платформы ---------- */

  function showPlatform(key) {
    const platform = PLATFORMS[key];
    if (!platform) return;
    const pack = platform[lang] || platform.ru;
    const body = $("#tab-body");

    const title = document.createElement("h4");
    title.textContent = platform.title;

    const ol = document.createElement("ol");
    for (const step of pack.steps) {
      const li = document.createElement("li");
      li.innerHTML = step;
      ol.appendChild(li);
    }
    const links = document.createElement("div");
    links.className = "links";
    for (const [label, href] of platform.links) {
      const a = document.createElement("a");
      a.className = "ghost-btn small";
      a.href = href;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = label;
      links.appendChild(a);
    }
    const hint = document.createElement("p");
    hint.className = "hint";
    hint.textContent = pack.hint;

    body.innerHTML = "";
    body.append(title, ol, links, hint);
  }

  /* ---------- копирование и QR ---------- */

  function initCopyAndQr() {
    document.addEventListener("click", async (ev) => {
      const copyEl = ev.target.closest("[data-copy-el]");
      if (copyEl) {
        const target = document.getElementById(copyEl.dataset.copyEl);
        const text = target ? target.textContent.trim() : (copyEl.dataset.copy || "");
        const ok = await copyText(text);
        if (copyEl.id === "hero-copy") {
          flashNote($("#copy-note"), ok ? t("copied") : t("copy_failed"), !ok);
          return;
        }
        const old = copyEl.textContent;
        copyEl.textContent = ok ? t("copied") : t("copy_failed");
        setTimeout(() => { copyEl.textContent = old; }, 1800);
        return;
      }

      const qrBtn = ev.target.closest("[data-qr-el]");
      if (qrBtn) {
        const target = document.getElementById(qrBtn.dataset.qrEl);
        const holder = qrBtn.closest(".link-card").querySelector(".qr");
        if (!holder || !target) return;
        if (!holder.hidden) { holder.hidden = true; qrBtn.textContent = t("qr"); return; }
        holder.innerHTML = "";
        if (typeof window.QRCode === "function") {
          new window.QRCode(holder, {
            text: target.textContent.trim(),
            width: 168,
            height: 168,
            colorDark: "#0a0e16",
            colorLight: "#ffffff",
            correctLevel: window.QRCode.CorrectLevel.M,
          });
          holder.hidden = false;
          qrBtn.textContent = t("hide_qr");
        } else {
          flashNote($("#copy-note"), "QR-библиотека не загрузилась", true);
        }
        return;
      }
    });
  }

  /* ---------- проверка ---------- */

  function relTime(date) {
    const diff = Date.now() - date.getTime();
    if (diff < 0) return lang === "ru" ? "только что" : "just now";
    const min = Math.floor(diff / 60000);
    if (min < 1) return lang === "ru" ? "меньше минуты назад" : "less than a minute ago";
    if (min < 60) return lang === "ru" ? `${min} мин назад` : `${min} min ago`;
    const h = Math.floor(min / 60);
    if (h < 24) return lang === "ru" ? `${h} ч назад` : `${h} h ago`;
    return lang === "ru" ? `${Math.floor(h / 24)} дн назад` : `${Math.floor(h / 24)} d ago`;
  }

  function parseUpdated(value) {
    if (!value) return null;
    const d = new Date(value.replace(" ", "T").replace(" UTC", "Z"));
    return Number.isNaN(d.getTime()) ? null : d;
  }

  async function runCheck() {
    const out = $("#check-out");
    const btn = $("#check-btn");
    btn.disabled = true;
    btn.textContent = t("check_running");
    out.innerHTML = "";

    const add = (k, v, cls = "") => {
      const li = document.createElement("li");
      const kk = document.createElement("span");
      kk.className = "k";
      kk.textContent = k;
      const vv = document.createElement("span");
      vv.className = "v " + cls;
      vv.textContent = v;
      li.append(kk, vv);
      out.appendChild(li);
    };

    const stats = await fetchText("stats.json", 8000);
    if (stats) {
      add(t("check_source"), stats.source, "ok");
      add(t("check_stats"), `${stats.ms} ms`, "ok");
      try {
        const data = JSON.parse(stats.text);
        const when = parseUpdated(data.updated);
        add(t("check_updated"), when ? `${data.updated} (${relTime(when)})` : String(data.updated));
        add(t("check_count"), String(data.published));
        if (typeof data.stable === "number") add(t("check_stable"), String(data.stable));
        if (typeof data.tls_ok === "number") add(t("card_tls"), `${data.tls_ok}`);
        const fresh = when && Date.now() - when.getTime() < 3 * 3600 * 1000;
        add(t("check_fresh"), fresh ? t("check_fresh_ok") : t("check_fresh_bad"), fresh ? "ok" : "bad");
      } catch (e) {
        add("stats.json", "битый ответ", "bad");
      }
    } else {
      add("stats.json", t("check_bad"), "bad");
    }

    const nodes = await fetchText("nodes.json", 12000);
    if (nodes) {
      try {
        const list = JSON.parse(nodes.text);
        add(t("check_nodes"), `${list.length} · ${nodes.source}, ${nodes.ms} ms`, "ok");
      } catch (e) {
        add(t("check_nodes"), "битый ответ", "bad");
      }
    } else {
      add(t("check_nodes"), t("check_bad"), "bad");
    }

    const stable = await fetchText("sub-stable.txt", 12000);
    if (stable) {
      const rows = stable.text.trim() ? stable.text.trim().split("\n").length : 0;
      if (rows) {
        add(t("check_stable_link"), `${rows} · ${stable.source}, ${stable.ms} ms`, "ok");
      } else {
        // Пустая стабильная подписка это не поломка: узлы ещё не набрали
        // нужное число прогонов подряд.
        add(t("check_stable_link"), t("check_stable_empty"));
      }
    } else {
      add(t("check_stable_link"), t("check_bad"), "bad");
    }

    const clash = await fetchText("clash.yaml", 12000);
    if (clash) {
      const proxies = (clash.text.match(/server: "/g) || []).length;
      add(t("check_clash"), `${proxies} · ${clash.source}, ${clash.ms} ms`, "ok");
    } else {
      add(t("check_clash"), t("check_bad"), "bad");
    }

    const probe = await fetchText("all.txt", 12000);
    if (probe) {
      const bytes = new Blob([probe.text]).size;
      const kbps = probe.ms > 0 ? Math.round((bytes / 1024) / (probe.ms / 1000)) : 0;
      const rows = probe.text.split("\n").filter((l) => l.trim()).length;
      add(t("check_rows"), `${rows} · ${probe.source}, ${probe.ms} ms`, "ok");
      add(t("check_size"), `${Math.round(bytes / 1024)} КБ`);
      add(t("check_speed"), `${kbps} КБ/с`, "ok");
    } else {
      add("all.txt", t("check_bad"), "bad");
    }

    btn.disabled = false;
    btn.textContent = t("check_btn");
  }

  /* ---------- язык ---------- */

  function applyLang(next) {
    lang = next;
    document.documentElement.lang = lang;
    try { localStorage.setItem("fvps-lang", lang); } catch (e) {}
    const btn = $("#lang-btn");
    if (btn) btn.textContent = lang === "ru" ? "RU" : "EN";

    $$("[data-i18n]").forEach((el) => { el.innerHTML = t(el.dataset.i18n); });
    $$("[data-i18n-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });

    const safety = $("#safety-body");
    if (safety) {
      safety.innerHTML = "";
      for (const paragraph of (TEXTS.safety[lang] || TEXTS.safety.ru)) {
        const p = document.createElement("p");
        p.textContent = paragraph;
        safety.appendChild(p);
      }
    }

    const activeTab = $(".tab.is-active");
    showPlatform(activeTab ? activeTab.dataset.tab : "windows");
    initDeepLinks();
    initLinks();
    renderChips();
    renderRows();
    updateBuilder();
    if (lastStats) {
      const status = $("#live-status");
      if (status) status.textContent = tf("status_loaded", { src: state.source });
      const upd = $("#live-updated");
      if (upd && lastStats.updated) upd.textContent = tf("updated", { when: lastStats.updated });
      applyStableTag(lastStats);
    }
  }

  /* ---------- запуск ---------- */

  function init() {
    applyTheme(document.documentElement.dataset.theme || "dark");
    applyLang(lang);
    initNet();
    initCopyAndQr();
    initBuilder();

    $("#theme-btn").addEventListener("click", () => {
      const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
      applyTheme(next);
    });

    $("#lang-btn").addEventListener("click", () => {
      applyLang(lang === "ru" ? "en" : "ru");
    });

    $$(".tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        $$(".tab").forEach((el) => {
          el.classList.toggle("is-active", el === tab);
          el.setAttribute("aria-selected", el === tab ? "true" : "false");
        });
        showPlatform(tab.dataset.tab);
      });
    });

    $("#node-search").addEventListener("input", (ev) => {
      board.query = ev.target.value;
      board.limit = 18;
      renderRows();
    });

    $("#only-stable").addEventListener("change", (ev) => {
      board.onlyStable = ev.target.checked;
      board.limit = 18;
      renderRows();
    });

    $("#sort-by").addEventListener("change", (ev) => {
      board.sort = ev.target.value;
      renderRows();
    });

    $("#more-btn").addEventListener("click", () => {
      board.limit += 18;
      renderRows();
    });

    $("#check-btn").addEventListener("click", runCheck);

    loadStats();
    loadNodes();

    // Офлайн-оболочка: страница открывается даже без сети. Данные в кэш
    // не кладём, они меняются каждый час. Нужен https или localhost,
    // иначе браузер откажется регистрировать воркер.
    const local = location.hostname === "localhost" || location.hostname === "127.0.0.1";
    if ("serviceWorker" in navigator && (location.protocol === "https:" || local)) {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
