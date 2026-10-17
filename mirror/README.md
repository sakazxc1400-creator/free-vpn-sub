# Зеркало на Cloudflare Workers

Зачем. `raw.githubusercontent.com` и сам GitHub Pages в России часто
недоступны, а jsdelivr иногда отвечает медленно. Воркер на Cloudflare
живёт на домене, который обычно открыт, и отдаёт те же файлы подписки.

Всё делается в браузере, ставить ничего не нужно.

## Как развернуть

1. Открой [dash.cloudflare.com](https://dash.cloudflare.com) и войди.
   Бесплатного аккаунта достаточно, карта не нужна.
2. Слева выбери `Workers & Pages` → `Create` → `Workers` →
   `Start from scratch`.
3. Имя воркера, например `free-vpn-sub`. Нажми `Deploy`.
4. Открой код воркера (`Edit code`), удали шаблон и вставь целиком
   содержимое [`worker.js`](worker.js) из этой папки.
5. Нажми `Deploy`. В адресной строке панели появится адрес вида
   `https://free-vpn-sub.ТВОЙ-АККАУНТ.workers.dev`.

Проверка: открой в браузере
`https://free-vpn-sub.ТВОЙ-АККАУНТ.workers.dev/sub.txt`. Должна
открыться base64-строка подписки.

## Что отдаёт воркер

| Адрес | Что это |
| --- | --- |
| `/sub.txt` | основная подписка (base64) |
| `/sub-stable.txt` | только узлы, живущие часами |
| `/sub-full.txt` | полная подписка (base64) |
| `/all.txt`, `/all-full.txt`, `/all-stable.txt` | те же списки обычным текстом |
| `/clash.yaml` | конфиг Clash / Mihomo |
| `/nodes.json` | данные для сайта и своя подписка |
| `/stats.json`, `/history.json` | статистика и история узлов |
| `/by-country/xx.txt` | узлы одной страны |

Остальные адреса воркер не обслуживает: он не должен превращаться в
открытый прокси.

## Дальше

Адрес зеркала можно вписать в клиент напрямую вместо ссылки на GitHub.
Чтобы оно появилось и на сайте, добавь его в `EXTRA_MIRRORS` в
`docs/app.js`:

```js
const EXTRA_MIRRORS = [
  ["cloudflare · основная", "https://free-vpn-sub.ТВОЙ-АККАУНТ.workers.dev/sub.txt"],
  ["cloudflare · стабильная", "https://free-vpn-sub.ТВОЙ-АККАУНТ.workers.dev/sub-stable.txt"],
  ["cloudflare · Clash", "https://free-vpn-sub.ТВОЙ-АККАУНТ.workers.dev/clash.yaml"],
];
```

## Сколько это стоит

Бесплатный тариф Workers: 100 000 запросов в сутки. Один клиент обычно
делает несколько запросов в час, так что предела хватает с запасом.
Файлы кэшируются на стороне Cloudflare на 5 минут, повторные запросы
не идут на GitHub.

## Если не хочется воркер

В подписках уже прописано зеркало jsdelivr, а на сайте есть список
готовых зеркал, включая `gh-proxy.com`, `ghproxy.net` и
`raw.githack.com`. Своего домена они не требуют.
