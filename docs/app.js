/* Free VPN Sub — логика сайта.
   Данные берутся из output/ репозитория: сначала пробуем raw.githubusercontent,
   если он недоступен, переключаемся на зеркало jsdelivr. */

(() => {
  "use strict";

  const REPO = "sakazxc1400-creator/free-vpn-sub";
  const BRANCH = "main";
  const RAW = `https://raw.githubusercontent.com/${REPO}/${BRANCH}/output/`;
  const CDN = `https://cdn.jsdelivr.net/gh/${REPO}@${BRANCH}/output/`;
  const GITHUB = `https://github.com/${REPO}`;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- сеть ---------- */

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
          return { text, ms: Math.round(performance.now() - started), source: base === RAW ? "raw" : "jsdelivr" };
        }
      } catch (err) {
        clearTimeout(timer);
      }
    }
    return null;
  }

  /* ---------- утилиты ---------- */

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function setNum(el, value) {
    if (value === null || value === undefined || Number.isNaN(value)) { el.textContent = "—"; return; }
    el.textContent = String(value);
  }

  function animateNum(el, target, suffix = "") {
    if (!Number.isFinite(target)) { setNum(el, target); return; }
    const final = target.toLocaleString("ru-RU") + suffix;
    if (reduceMotion) { el.textContent = final; return; }
    const dur = 900;
    const t0 = performance.now();
    let done = false;
    // requestAnimationFrame не работает в фоновой вкладке, поэтому финальное
    // число всё равно выставляем по таймеру: иначе останется заглушка.
    const finish = () => { if (!done) { done = true; el.textContent = final; } };
    const step = (now) => {
      if (done) return;
      const p = Math.min(1, (now - t0) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased).toLocaleString("ru-RU") + suffix;
      if (p < 1) requestAnimationFrame(step);
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
    el.textContent = message;
    el.style.color = bad ? "var(--danger)" : "var(--teal)";
    clearTimeout(el._timer);
    el._timer = setTimeout(() => { el.textContent = ""; }, 3200);
  }

  /* ---------- разбор строки подписки ---------- */

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

    return {
      base,
      flag,
      country,
      proto,
      ms: Number.isFinite(ms) ? ms : null,
      addr: hostOf(base),
    };
  }

  /* ---------- фон: дрейфующая сеть ---------- */

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
            const a = (1 - d / linkDist) * 0.16;
            ctx.strokeStyle = `rgba(120, 150, 200, ${a})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.stroke();
          }
        }
      }
      for (const n of nodes) {
        ctx.fillStyle = "rgba(244, 185, 66, 0.5)";
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
      if (reduceMotion) {
        fill.style.width = pct + "%";
      } else {
        // Полоска должна быть видна и в фоновой вкладке, где rAF приостановлен.
        requestAnimationFrame(() => { fill.style.width = pct + "%"; });
        setTimeout(() => { fill.style.width = pct + "%"; }, 60);
      }
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

  async function loadStats() {
    const res = await fetchText("stats.json");
    if (!res) return null;
    let data;
    try { data = JSON.parse(res.text); } catch (e) { return null; }

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

    const status = $("#live-status");
    if (status) status.textContent = `Подписка обновлена, источник ${res.source}`;

    const upd = $("#live-updated");
    if (upd && data.updated) upd.textContent = `обновление: ${data.updated}`;

    const protos = Object.entries(data.by_protocol || {}).sort((a, b) => b[1] - a[1]);
    renderBars($("#proto-bars"), protos, { format: (p) => p });

    const countries = Object.entries(data.by_country || {}).slice(0, 12);
    renderBars($("#country-bars"), countries, { format: (c) => `${flagOf(c)} ${c}` });

    return data;
  }

  /* ---------- доска узлов ---------- */

  const board = {
    rows: [],
    proto: "",
    query: "",
    limit: 18,
  };

  function renderChips() {
    const counts = new Map();
    for (const r of board.rows) counts.set(r.proto, (counts.get(r.proto) || 0) + 1);
    const container = $("#proto-chips");
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
    make(`Все · ${board.rows.length}`, "");
    for (const [proto, n] of [...counts.entries()].sort((a, b) => b[1] - a[1])) {
      make(`${proto} · ${n}`, proto);
    }
  }

  function filtered() {
    const q = board.query.trim().toLowerCase();
    return board.rows.filter((r) => {
      if (board.proto && r.proto !== board.proto) return false;
      if (q && !(r.country.toLowerCase().includes(q) || r.addr.toLowerCase().includes(q))) return false;
      return true;
    });
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
      cname.textContent = r.country;
      who.append(flag, cname);

      const proto = document.createElement("span");
      proto.className = "proto";
      proto.textContent = r.proto;

      const lat = document.createElement("span");
      lat.className = "lat";
      const num = document.createElement("span");
      num.className = "lat-num";
      num.textContent = r.ms === null ? "—" : `${r.ms}ms`;
      const meter = document.createElement("span");
      meter.className = "meter";
      const fill = document.createElement("i");
      if (r.ms !== null && maxMs > minMs) {
        const speed = (maxMs - r.ms) / (maxMs - minMs);
        fill.style.width = `${Math.round(6 + speed * 94)}%`;
      } else {
        fill.style.width = "30%";
      }
      meter.appendChild(fill);
      lat.append(num, meter);

      const addr = document.createElement("span");
      addr.className = "addr";
      addr.textContent = r.addr;

      li.append(idx, who, proto, lat, addr);
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
      ? `Показано ${shown.length} из ${rows.length} узлов этой подписки`
      : "Ничего не найдено, сбрось фильтр";
  }

  async function loadNodes() {
    const res = await fetchText("all.txt");
    const note = $("#board-note");
    if (!res) {
      note.textContent = "Не удалось загрузить список. Проверь ссылку на подписку вручную.";
      return;
    }
    board.rows = res.text.split("\n").map(parseLine).filter(Boolean).map((r, i) => ({ ...r, i: i + 1 }));
    renderChips();
    renderRows();
  }

  /* ---------- ссылки и зеркала ---------- */

  function initLinks() {
    const mainRaw = `${RAW}sub.txt`;
    const fullRaw = `${RAW}sub-full.txt`;
    $("#url-main").textContent = mainRaw;
    $("#url-full").textContent = fullRaw;
    $("#dl-main").href = `${RAW}all.txt`;
    $("#dl-full").href = `${RAW}all-full.txt`;

    const mirrors = [
      ["jsdelivr · основная", `${CDN}sub.txt`],
      ["gh-proxy · основная", `https://gh-proxy.com/${mainRaw}`],
      ["raw · основная", mainRaw],
      ["jsdelivr · полная", `${CDN}sub-full.txt`],
      ["gh-proxy · полная", `https://gh-proxy.com/${fullRaw}`],
      ["raw · полная", fullRaw],
    ];
    const list = $("#mirror-list");
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
      btn.textContent = "Копировать";
      btn.addEventListener("click", async () => {
        const ok = await copyText(url);
        btn.textContent = ok ? "Скопировано" : "Не вышло";
        setTimeout(() => { btn.textContent = "Копировать"; }, 1800);
      });
      row.append(label, code, btn);
      list.appendChild(row);
    }
  }

  /* ---------- платформы ---------- */

  const PLATFORMS = {
    windows: {
      title: "Windows",
      steps: [
        "Скачай <a href=\"https://github.com/MatsuriDayo/nekoray/releases\" target=\"_blank\" rel=\"noopener\">Nekoray</a>, архив <code>nekoray-*-windows64.zip</code>, и распакуй его.",
        "В настройках выбери ядро <strong>sing-box</strong>.",
        "Добавь профиль из подписки и вставь ссылку.",
        "Обнови подписки, выбери сервер сверху списка и нажми <kbd>Enter</kbd>.",
        "Нажми <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>S</kbd>, чтобы включить системный прокси.",
      ],
      hint: "Вместо Nekoray можно взять v2rayN, ссылка добавляется в разделе «Подписки».",
      links: [["Nekoray", "https://github.com/MatsuriDayo/nekoray/releases"], ["v2rayN", "https://github.com/2dust/v2rayN/releases"]],
    },
    android: {
      title: "Android",
      steps: [
        "Установи v2rayNG или Hiddify.",
        "Открой настройки групп подписок и нажми <kbd>+</kbd>.",
        "Вставь ссылку и сохрани.",
        "Обнови подписки, выбери сервер и подключись.",
      ],
      hint: "Для Hysteria2 и TUIC удобнее Hiddify. Подписка добавляется через «+» и «Добавить из ссылки».",
      links: [["v2rayNG", "https://github.com/2dust/v2rayNG/releases"], ["Hiddify", "https://github.com/hiddify/hiddify-next/releases"]],
    },
    ios: {
      title: "iPhone и iPad",
      steps: [
        "Поставь Streisand, v2Box или Shadowrocket. Первые два бесплатные.",
        "Открой раздел подписок и нажми <kbd>+</kbd>.",
        "Вставь ссылку и обнови список.",
        "Выбери сервер и подключись.",
      ],
      hint: "Shadowrocket платный, но стабильнее остальных.",
      links: [],
    },
    macos: {
      title: "macOS",
      steps: [
        "Возьми Hiddify или V2RayXS.",
        "Добавь подписку по ссылке.",
        "Обнови список и подключись к серверу.",
      ],
      hint: "Hiddify в формате dmg, V2RayXS ставится через Homebrew.",
      links: [["Hiddify", "https://github.com/hiddify/hiddify-next/releases"]],
    },
    linux: {
      title: "Linux",
      steps: [
        "Скачай Nekoray или Hiddify в формате AppImage.",
        "Дай файлу право на запуск: <code>chmod +x имя.AppImage</code>.",
        "Добавь подписку, обнови список и выбери сервер.",
      ],
      hint: "Nekoray использует ядро sing-box, Hiddify удобнее для Hysteria2 и TUIC.",
      links: [["Nekoray", "https://github.com/MatsuriDayo/nekoray/releases"], ["Hiddify", "https://github.com/hiddify/hiddify-next/releases"]],
    },
  };

  function showPlatform(key) {
    const p = PLATFORMS[key];
    if (!p) return;
    const body = $("#tab-body");
    const ol = document.createElement("ol");
    for (const step of p.steps) {
      const li = document.createElement("li");
      li.innerHTML = step;
      ol.appendChild(li);
    }
    const links = document.createElement("div");
    links.className = "links";
    for (const [label, href] of p.links) {
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
    hint.textContent = p.hint;

    body.innerHTML = "";
    body.append(ol, links, hint);
  }

  /* ---------- копирование и QR ---------- */

  function initCopyAndQr() {
    document.addEventListener("click", async (ev) => {
      const copyEl = ev.target.closest("[data-copy-el]");
      if (copyEl) {
        const target = document.getElementById(copyEl.dataset.copyEl);
        const ok = await copyText(target ? target.textContent.trim() : "");
        const old = copyEl.textContent;
        copyEl.textContent = ok ? "Скопировано" : "Не вышло";
        setTimeout(() => { copyEl.textContent = old; }, 1800);
        return;
      }

      const qrBtn = ev.target.closest("[data-qr-el]");
      if (qrBtn) {
        const target = document.getElementById(qrBtn.dataset.qrEl);
        const holder = qrBtn.closest(".link-card").querySelector(".qr");
        if (!holder || !target) return;
        if (!holder.hidden) { holder.hidden = true; qrBtn.textContent = "QR-код"; return; }
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
          qrBtn.textContent = "Скрыть QR";
        } else {
          flashNote($("#copy-note"), "QR-библиотека не загрузилась", true);
        }
        return;
      }

      const hero = ev.target.closest("#hero-copy");
      if (hero) {
        const ok = await copyText(hero.dataset.copy);
        flashNote($("#copy-note"), ok ? "Основная подписка скопирована. Вставь её в клиент." : "Не удалось скопировать, выдели ссылку вручную.", !ok);
      }
    });
  }

  /* ---------- проверка ---------- */

  function relTime(date) {
    const diff = Date.now() - date.getTime();
    if (diff < 0) return "только что";
    const min = Math.floor(diff / 60000);
    if (min < 1) return "меньше минуты назад";
    if (min < 60) return `${min} мин назад`;
    const h = Math.floor(min / 60);
    if (h < 24) return `${h} ч назад`;
    return `${Math.floor(h / 24)} дн назад`;
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
    btn.textContent = "Проверяю…";
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
      add("источник данных", stats.source, "ok");
      add("stats.json загружен", `${stats.ms} ms`, "ok");
      try {
        const data = JSON.parse(stats.text);
        const when = parseUpdated(data.updated);
        add("список обновлён", when ? `${data.updated} (${relTime(when)})` : String(data.updated));
        add("серверов в подписке", String(data.published));
        const fresh = when && Date.now() - when.getTime() < 3 * 3600 * 1000;
        add("свежесть", fresh ? "свежий" : "давно не обновлялся", fresh ? "ok" : "bad");
      } catch (e) {
        add("stats.json", "битый ответ", "bad");
      }
    } else {
      add("stats.json", "недоступен ни на raw, ни на jsdelivr", "bad");
    }

    const probe = await fetchText("all.txt", 12000);
    if (probe) {
      const bytes = new Blob([probe.text]).size;
      const kbps = probe.ms > 0 ? Math.round((bytes / 1024) / (probe.ms / 1000)) : 0;
      add("список all.txt", `${probe.source}, ${probe.ms} ms`, "ok");
      add("размер списка", `${Math.round(bytes / 1024)} КБ`);
      add("скорость загрузки", `${kbps} КБ/с`, "ok");
    } else {
      add("all.txt", "не загрузился", "bad");
    }

    btn.disabled = false;
    btn.textContent = "Проверить сейчас";
  }

  /* ---------- запуск ---------- */

  function init() {
    initNet();
    initCopyAndQr();
    initLinks();
    showPlatform("windows");

    $$(".tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        $$(".tab").forEach((t) => {
          t.classList.toggle("is-active", t === tab);
          t.setAttribute("aria-selected", t === tab ? "true" : "false");
        });
        showPlatform(tab.dataset.tab);
      });
    });

    $("#node-search").addEventListener("input", (ev) => {
      board.query = ev.target.value;
      board.limit = 18;
      renderRows();
    });

    $("#more-btn").addEventListener("click", () => {
      board.limit += 18;
      renderRows();
    });

    $("#check-btn").addEventListener("click", runCheck);

    loadStats();
    loadNodes();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
