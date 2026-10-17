// Файлы подписки лежат в ветке data, ссылки собираются тут же.

const REPO = "sakazxc1400-creator/free-vpn-sub";
const BRANCH = "data";
const RAW = `https://raw.githubusercontent.com/${REPO}/${BRANCH}/output/`;

// Сначала raw, если он не открывается, идём по зеркалам.
const SOURCES = [
  ["raw.githubusercontent", RAW],
  ["jsdelivr", `https://cdn.jsdelivr.net/gh/${REPO}@${BRANCH}/output/`],
  ["gh-proxy.com", "https://gh-proxy.com/" + RAW],
  ["ghproxy.net", "https://ghproxy.net/" + RAW],
  ["githack", `https://raw.githack.com/${REPO}/${BRANCH}/output/`],
];

const SUBS = [
  ["Основная", "200 самых быстрых", RAW + "sub.txt"],
  ["Стабильная", "эти серверы живут уже 6 прогонов", RAW + "sub-stable.txt"],
  ["Полная", "все живые серверы", RAW + "sub-full.txt"],
  ["Clash", "для Clash Verge, FlClash и Mihomo", RAW + "clash.yaml"],
];

const state = document.getElementById("state");
const nums = document.getElementById("nums");
const subs = document.getElementById("subs");
const mirrors = document.getElementById("mirrors");
const deep = document.getElementById("deep");

function plural(n, one, few, many) {
  const a = n % 10;
  const b = n % 100;
  if (a === 1 && b !== 11) return `${n} ${one}`;
  if (a >= 2 && a <= 4 && (b < 10 || b >= 20)) return `${n} ${few}`;
  return `${n} ${many}`;
}

function ago(stamp) {
  const t = Date.parse(stamp.replace(" UTC", "Z").replace(" ", "T"));
  if (!t) return "недавно";
  const min = Math.round((Date.now() - t) / 60000);
  if (min < 1) return "только что";
  if (min < 60) return plural(min, "минуту", "минуты", "минут") + " назад";
  const h = Math.round(min / 60);
  if (h < 24) return plural(h, "час", "часа", "часов") + " назад";
  return plural(Math.round(h / 24), "день", "дня", "дней") + " назад";
}

function num(v) {
  return typeof v === "number" ? v.toLocaleString("ru-RU") : v;
}

// Подписки.

for (const [name, note, url] of SUBS) {
  const li = document.createElement("li");
  li.innerHTML = `<div class="sub-head"><b>${name}</b><span class="note">${note}</span></div>
    <code>${url}</code>
    <div class="row">
      <button class="copy" type="button" data-copy="${url}">копировать</button>
      <a href="${url}" target="_blank" rel="noopener">открыть файл</a>
    </div>`;
  subs.append(li);
}

// Кнопки для тех, у кого клиент уже стоит.

const main = SUBS[0][2];
const deepLinks = [
  ["Hiddify", `hiddify://import/${main}#FreeVPNSub`],
  ["v2rayNG", `v2rayng://install-sub?url=${encodeURIComponent(main)}#FreeVPNSub`],
  ["sing-box", `sing-box://import-remote-profile?url=${encodeURIComponent(main)}#FreeVPNSub`],
];

deepLinks.forEach(([name, href], i) => {
  if (i) deep.append(", ");
  const a = document.createElement("a");
  a.textContent = name;
  a.href = href;
  deep.append(a);
});

// Зеркала: там те же файлы, только хост другой.

for (const [host, base] of SOURCES) {
  const url = base + "sub.txt";
  const li = document.createElement("li");
  li.innerHTML = `<span class="host">${host}</span>
    <code>${url}</code>
    <button class="copy" type="button" data-copy="${url}">копировать</button>`;
  mirrors.append(li);
}

// Состояние последнего прогона беру из stats.json, перебирая хосты по очереди.

async function loadStats() {
  for (const [, base] of SOURCES) {
    try {
      const r = await fetch(base + "stats.json", { cache: "no-store" });
      if (r.ok) return await r.json();
    } catch (e) {
      // хост не ответил, пробую следующий
    }
  }
  return null;
}

loadStats().then((d) => {
  if (!d) {
    state.textContent = "статистику загрузить не вышло, но ссылки выше рабочие";
    return;
  }

  const parts = [];
  if (d.updated) parts.push("обновлено " + ago(d.updated));
  if (d.published) parts.push(num(d.published) + " серверов");
  if (d.countries) parts.push(d.countries + " стран");
  if (d.best_latency_ms) parts.push("лучший пинг " + d.best_latency_ms + " мс");
  state.textContent = parts.join(", ");

  const rows = [
    ["конфигов нашлось", num(d.unique)],
    ["ответили на проверку порта", num(d.tcp_alive)],
    ["реально работают", num(d.verified)],
    ["в основной подписке", num(d.published)],
    [`держатся ${d.stable_runs || 6} прогонов подряд`, num(d.stable)],
    ["стран", num(d.countries)],
    ["пинг лучшего сервера", d.best_latency_ms ? d.best_latency_ms + " мс" : null],
    ["скорость лучшего сервера", d.best_speed_mbps ? d.best_speed_mbps + " Мбит/с" : null],
  ];

  for (const [label, value] of rows) {
    if (value == null) continue;
    const li = document.createElement("li");
    li.innerHTML = `<span>${label}</span><span class="val">${value}</span>`;
    nums.append(li);
  }
});

// Копирование: и подписки, и адрес для донатов.

function textToCopy(btn) {
  const target = document.getElementById(btn.dataset.copy);
  return target ? target.textContent.trim() : btn.dataset.copy;
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (e) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.append(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  }
}

document.addEventListener("click", async (e) => {
  const btn = e.target.closest("button.copy");
  if (!btn) return;
  const ok = await copyText(textToCopy(btn));
  btn.textContent = ok ? "скопировано" : "не вышло";
  btn.classList.toggle("done", ok);
  setTimeout(() => {
    btn.textContent = "копировать";
    btn.classList.remove("done");
  }, 1500);
});

// PWA тут больше нет, но у старых посетителей остался воркер с кэшем страницы.
// Пусть проверит обновление и снимет себя.

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.getRegistrations()
    .then((list) => list.forEach((r) => r.update().catch(() => {})))
    .catch(() => {});
}
