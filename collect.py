#!/usr/bin/env python3
"""
Агрегатор бесплатных VPN-подписок.

Что делает:
  1. Скачивает конфиги из списка источников (sources.txt).
  2. Понимает форматы: plain-text и base64.
  3. Извлекает ссылки протоколов vless/vmess/trojan/ss/hysteria2/tuic.
  4. Убирает дубликаты по реальному адресу сервера (а не по тексту ссылки).
  5. Отсеивает мёртвые узлы TCP-проверкой, затем прогоняет выживших через
     sing-box и оставляет только те, через которые реально идёт трафик.
  6. Определяет страну каждого узла и подписывает её флагом в названии.
  7. Складывает результат в output/sub.txt (base64) + файлы по протоколам
     и по странам.

Зависимостей нет — только стандартная библиотека Python 3.9+.
Для настоящей проверки нужен бинарник sing-box; без него используется
TCP-проверка.
"""

from __future__ import annotations

import base64
import binascii
import ipaddress
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import geo
import probe

# ----------------------------------------------------------------------------
# Настройки
# ----------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
SOURCES_FILE = ROOT / "sources.txt"
OUTPUT_DIR = ROOT / "output"

PROTOCOLS = ("vless", "vmess", "trojan", "ss", "hysteria2", "hy2", "tuic")

# Регулярка для вылавливания ссылок из произвольного текста.
LINK_RE = re.compile(
    r"\b(?:" + "|".join(PROTOCOLS) + r")://[^\s\"'<>\\]+",
    re.IGNORECASE,
)

FETCH_TIMEOUT = 25          # сек на скачивание одного источника
FETCH_RETRIES = 3           # попыток на источник
FETCH_WORKERS = 12          # параллельных загрузок

CHECK_TIMEOUT = 3.0         # сек на TCP-коннект к узлу
CHECK_WORKERS = 200         # параллельных проверок
CHECK_LIMIT = 6000          # максимум узлов, отправляемых на TCP-проверку

# Размер итоговой подписки. Держим небольшим: клиенту не нужны тысячи
# серверов, ему нужны несколько десятков рабочих.
MAX_OUTPUT = 100

# Сколько кандидатов прогонять через sing-box. Берём с запасом, потому что
# доля реально работающих узлов — обычно 10-30%.
VERIFY_CANDIDATES = 900

# Протоколы поверх QUIC/UDP. TCP-коннектом их проверить нельзя — порт
# на TCP закрыт даже у полностью рабочего сервера, поэтому они идут сразу
# в sing-box, минуя TCP-фильтр.
UDP_PROTOCOLS = frozenset({"hysteria2", "tuic"})

# Сколько узлов на одну страну максимум, чтобы список не заполнился
# двадцатью серверами из одного датацентра.
MAX_PER_COUNTRY = 12

USER_AGENT = "Mozilla/5.0 (compatible; free-vpn-sub/1.0; +https://github.com)"

# Зеркала для raw.githubusercontent.com: в части сетей он заблокирован,
# и без обхода локальный запуск скрипта невозможен.
RAW_HOST = "raw.githubusercontent.com"
MIRROR_TEMPLATES = (
    "https://gh-proxy.com/https://{raw}",
    "https://raw.gitcode.host/{path}",
)

# Порты, которых в валидном конфиге быть не может.
VALID_PORT_RANGE = range(1, 65536)


# ----------------------------------------------------------------------------
# Модель узла
# ----------------------------------------------------------------------------

@dataclass
class Node:
    """Один VPN-узел."""

    raw: str                       # исходная ссылка
    proto: str                     # нормализованный протокол
    host: str                      # домен или IP
    port: int
    ident: str                     # ключ дедупликации
    latency_ms: int | None = None  # заполняется после проверки
    country: str = ""              # код страны, ISO 3166-1 alpha-2
    verified: bool = False         # прошёл ли проверку через sing-box

    @property
    def key(self) -> str:
        return self.ident


@dataclass
class Stats:
    """Счётчики для отчёта."""

    sources_total: int = 0
    sources_ok: int = 0
    sources_failed: list[str] = field(default_factory=list)
    links_found: int = 0
    parsed: int = 0
    unique: int = 0
    tcp_alive: int = 0
    verified: int = 0
    alive: int = 0
    by_proto: dict[str, int] = field(default_factory=dict)
    by_country: dict[str, int] = field(default_factory=dict)


# ----------------------------------------------------------------------------
# Утилиты
# ----------------------------------------------------------------------------

def log(msg: str) -> None:
    print(msg, flush=True)


def b64_decode_loose(data: str) -> str | None:
    """
    Декодирует base64, прощая отсутствие padding и url-safe алфавит.
    Возвращает None, если это не base64.
    """
    cleaned = re.sub(r"\s+", "", data)
    if not cleaned or len(cleaned) < 16:
        return None
    if not re.fullmatch(r"[A-Za-z0-9+/=_-]+", cleaned):
        return None

    cleaned = cleaned.replace("-", "+").replace("_", "/")
    cleaned += "=" * (-len(cleaned) % 4)
    try:
        decoded = base64.b64decode(cleaned, validate=False)
    except (binascii.Error, ValueError):
        return None
    try:
        return decoded.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return decoded.decode("utf-8", errors="ignore") or None


def normalize_host(host: str) -> str:
    """Приводит хост к каноническому виду: нижний регистр, без скобок IPv6."""
    host = host.strip().lower().rstrip(".")
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    return host


def is_routable(host: str) -> bool:
    """Отсеивает localhost, приватные и служебные адреса."""
    if not host or host in {"localhost", "0.0.0.0", "::", "example.com"}:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # Домен: проверяем, что он вообще похож на домен.
        return bool(re.fullmatch(r"[a-z0-9._-]+\.[a-z]{2,}", host))
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


# ----------------------------------------------------------------------------
# Скачивание источников
# ----------------------------------------------------------------------------

def read_sources() -> list[str]:
    if not SOURCES_FILE.exists():
        log(f"[!] Нет файла {SOURCES_FILE.name}")
        return []
    urls: list[str] = []
    for line in SOURCES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    # Убираем дубли, сохраняя порядок.
    return list(dict.fromkeys(urls))


def mirror_urls(url: str) -> list[str]:
    """
    Для ссылок на raw.githubusercontent.com добавляет зеркала.
    В CI прямой доступ есть и зеркала не понадобятся, но при локальном
    запуске из сети с блокировками они спасают прогон.
    """
    if RAW_HOST not in url:
        return [url]
    raw = url.split("://", 1)[-1]
    path = raw[len(RAW_HOST) + 1:] if raw.startswith(RAW_HOST + "/") else raw
    variants = [url]
    for template in MIRROR_TEMPLATES:
        variants.append(template.format(raw=raw, path=path))
    return variants


def fetch(url: str) -> str | None:
    """
    Скачивает URL с retry. Если основной адрес недоступен, пробует зеркала.
    """
    last_error: str = ""
    for candidate in mirror_urls(url):
        req = urllib.request.Request(
            candidate, headers={"User-Agent": USER_AGENT}
        )
        for attempt in range(1, FETCH_RETRIES + 1):
            try:
                with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
                    body = resp.read().decode("utf-8", errors="ignore")
                if body.strip():
                    return body
                last_error = "пустой ответ"
                break
            except (urllib.error.URLError, urllib.error.HTTPError,
                    socket.timeout, ConnectionError, TimeoutError,
                    OSError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < FETCH_RETRIES:
                    time.sleep(1.5 * attempt)
    log(f"    [x] {url} -> {last_error}")
    return None


def extract_links(payload: str) -> list[str]:
    """
    Достаёт ссылки из текста. Если прямых ссылок нет — пробует
    декодировать всё содержимое как base64 и повторить.
    """
    links = LINK_RE.findall(payload)
    if links:
        return links
    decoded = b64_decode_loose(payload)
    if decoded:
        return LINK_RE.findall(decoded)
    return []


# ----------------------------------------------------------------------------
# Парсинг ссылок
# ----------------------------------------------------------------------------

def parse_vmess(link: str) -> Node | None:
    """vmess:// + base64(JSON)."""
    payload = link[len("vmess://"):]
    decoded = b64_decode_loose(payload)
    if not decoded:
        return None
    try:
        cfg = json.loads(decoded)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(cfg, dict):
        return None

    host = normalize_host(str(cfg.get("add", "")))
    try:
        port = int(str(cfg.get("port", "0")).strip())
    except (ValueError, TypeError):
        return None
    uuid = str(cfg.get("id", "")).strip().lower()

    if not host or port not in VALID_PORT_RANGE or not uuid:
        return None
    if not is_routable(host):
        return None

    return Node(
        raw=link,
        proto="vmess",
        host=host,
        port=port,
        ident=f"vmess|{host}|{port}|{uuid}",
    )


def parse_ss(link: str) -> Node | None:
    """
    ss:// в двух вариантах:
      ss://base64(method:pass)@host:port
      ss://base64(method:pass@host:port)
    """
    body = link[len("ss://"):]
    body = body.split("#", 1)[0]          # убираем remark
    body = body.split("?", 1)[0]          # убираем plugin-параметры

    if "@" not in body:
        decoded = b64_decode_loose(body)
        if not decoded or "@" not in decoded:
            return None
        body = decoded

    creds, _, endpoint = body.rpartition("@")
    if not endpoint:
        return None

    host, port = split_host_port(endpoint)
    if host is None or port is None:
        return None

    return Node(
        raw=link,
        proto="ss",
        host=host,
        port=port,
        ident=f"ss|{host}|{port}|{creds[:24]}",
    )


def split_host_port(endpoint: str) -> tuple[str | None, int | None]:
    """Разбирает 'host:port' и '[ipv6]:port'."""
    endpoint = endpoint.strip().strip("/")
    if not endpoint:
        return None, None

    if endpoint.startswith("["):
        close = endpoint.find("]")
        if close == -1:
            return None, None
        host = endpoint[1:close]
        rest = endpoint[close + 1:]
        if not rest.startswith(":"):
            return None, None
        port_str = rest[1:]
    else:
        if ":" not in endpoint:
            return None, None
        host, _, port_str = endpoint.rpartition(":")

    host = normalize_host(host)
    try:
        port = int(port_str)
    except (ValueError, TypeError):
        return None, None

    if port not in VALID_PORT_RANGE or not is_routable(host):
        return None, None
    return host, port


def parse_uri_style(link: str, proto: str) -> Node | None:
    """
    Общий разбор для vless / trojan / hysteria2 / tuic:
      proto://userinfo@host:port?params#remark
    """
    try:
        parsed = urllib.parse.urlsplit(link)
    except ValueError:
        return None

    host = normalize_host(parsed.hostname or "")
    port = parsed.port
    if port is None:
        # У hysteria2/tuic порт иногда опускают — тогда узел бесполезен.
        return None
    if not host or port not in VALID_PORT_RANGE or not is_routable(host):
        return None

    user = (parsed.username or "").strip().lower()
    if proto in ("vless", "trojan") and not user:
        return None

    # sni/host влияют на то, разный это узел или нет.
    qs = urllib.parse.parse_qs(parsed.query)
    sni = (qs.get("sni") or qs.get("host") or [""])[0].lower()

    return Node(
        raw=link,
        proto=proto,
        host=host,
        port=port,
        ident=f"{proto}|{host}|{port}|{user[:36]}|{sni}",
    )


def parse_link(link: str) -> Node | None:
    """Единая точка входа парсинга. Никогда не бросает исключений."""
    link = link.strip().rstrip(",;")
    scheme = link.split("://", 1)[0].lower() if "://" in link else ""

    try:
        if scheme == "vmess":
            return parse_vmess(link)
        if scheme == "ss":
            return parse_ss(link)
        if scheme in ("hysteria2", "hy2"):
            node = parse_uri_style(link, "hysteria2")
            return node
        if scheme in ("vless", "trojan", "tuic"):
            return parse_uri_style(link, scheme)
    except Exception:
        # Битые ссылки в публичных подписках — норма. Молча пропускаем.
        return None
    return None


# ----------------------------------------------------------------------------
# Проверка живости
# ----------------------------------------------------------------------------

def tcp_ping(node: Node) -> tuple[Node, int | None]:
    """TCP-коннект к узлу. Возвращает задержку в мс или None."""
    start = time.perf_counter()
    try:
        with socket.create_connection((node.host, node.port), timeout=CHECK_TIMEOUT):
            elapsed = int((time.perf_counter() - start) * 1000)
            return node, elapsed
    except (OSError, socket.timeout, ValueError):
        return node, None


def dns_ok(node: Node) -> tuple[Node, bool]:
    """
    Для UDP-протоколов (hysteria2/tuic) TCP-коннект бессмыслен.
    Проверяем хотя бы то, что хост разрешается в адрес.
    """
    try:
        socket.getaddrinfo(node.host, node.port, proto=socket.IPPROTO_UDP)
        return node, True
    except (OSError, socket.gaierror, ValueError):
        return node, False


def check_udp(nodes: list[Node]) -> list[Node]:
    """DNS-проверка UDP-узлов. Задержку не измеряем — её не с чего измерить."""
    ok: list[Node] = []
    if not nodes:
        return ok
    with ThreadPoolExecutor(max_workers=min(CHECK_WORKERS, 60)) as pool:
        futures = [pool.submit(dns_ok, n) for n in nodes]
        for fut in as_completed(futures):
            try:
                node, alive = fut.result()
            except Exception:
                continue
            if alive:
                ok.append(node)
    return ok


def check_alive(nodes: list[Node]) -> list[Node]:
    """Параллельно проверяет узлы, возвращает живые, отсортированные по latency."""
    alive: list[Node] = []
    done = 0
    total = len(nodes)

    with ThreadPoolExecutor(max_workers=CHECK_WORKERS) as pool:
        futures = {pool.submit(tcp_ping, n): n for n in nodes}
        for fut in as_completed(futures):
            done += 1
            if done % 500 == 0 or done == total:
                log(f"    проверено {done}/{total}, живых {len(alive)}")
            try:
                node, latency = fut.result()
            except Exception:
                continue
            if latency is not None:
                node.latency_ms = latency
                alive.append(node)

    alive.sort(key=lambda n: (n.latency_ms if n.latency_ms is not None else 9999))
    return alive


# ----------------------------------------------------------------------------
# Запись результатов
# ----------------------------------------------------------------------------

def retag(node: Node, index: int) -> str:
    """
    Переписывает название узла так, чтобы в клиенте сразу было видно
    страну, протокол и задержку:  🇳🇱 Нидерланды · vless · 84ms
    """
    parts: list[str] = []
    if node.country:
        parts.append(f"{geo.flag(node.country)} {geo.country_name(node.country)}")
    else:
        parts.append("🏴 ??")
    parts.append(node.proto)
    if node.latency_ms is not None:
        parts.append(f"{node.latency_ms}ms")

    label = f"{index:02d}. " + " · ".join(parts)
    tag = urllib.parse.quote(label, safe="")
    base = node.raw.split("#", 1)[0]
    return f"{base}#{tag}"


def write_outputs(nodes: list[Node], stats: Stats) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    tagged = [retag(n, i + 1) for i, n in enumerate(nodes)]
    plain = "\n".join(tagged)

    # Главная подписка — base64 (её понимают все клиенты).
    (OUTPUT_DIR / "sub.txt").write_text(
        base64.b64encode(plain.encode("utf-8")).decode("ascii"),
        encoding="utf-8",
    )
    # Тот же список в открытом виде — удобно смотреть глазами.
    (OUTPUT_DIR / "all.txt").write_text(plain + "\n", encoding="utf-8")

    # Разбивка по протоколам. Старые файлы удаляем: если в этот раз,
    # например, не нашлось ни одного tuic, файл с прошлого прогона
    # не должен вводить в заблуждение.
    known_protos = {"vless", "vmess", "trojan", "ss", "hysteria2", "tuic"}
    for proto in known_protos:
        stale = OUTPUT_DIR / f"{proto}.txt"
        if stale.exists():
            stale.unlink()

    by_proto: dict[str, list[str]] = {}
    for node, line in zip(nodes, tagged):
        by_proto.setdefault(node.proto, []).append(line)
    for proto, lines in by_proto.items():
        (OUTPUT_DIR / f"{proto}.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
    stats.by_proto = {p: len(v) for p, v in sorted(by_proto.items())}

    # Разбивка по странам — отдельной папкой, чтобы не мешалась в корне.
    country_dir = OUTPUT_DIR / "by-country"
    country_dir.mkdir(exist_ok=True)
    for stale in country_dir.glob("*.txt"):
        stale.unlink()

    by_country: dict[str, list[str]] = {}
    for node, line in zip(nodes, tagged):
        by_country.setdefault(node.country or "XX", []).append(line)
    for code, lines in by_country.items():
        (country_dir / f"{code.lower()}.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
    stats.by_country = {
        code: len(lines)
        for code, lines in sorted(
            by_country.items(), key=lambda kv: (-len(kv[1]), kv[0])
        )
    }

    latencies = [n.latency_ms for n in nodes if n.latency_ms is not None]

    report = {
        "updated": updated,
        "sources_total": stats.sources_total,
        "sources_ok": stats.sources_ok,
        "sources_failed": stats.sources_failed,
        "links_found": stats.links_found,
        "parsed": stats.parsed,
        "unique": stats.unique,
        "tcp_alive": stats.tcp_alive,
        "verified": stats.verified,
        "published": len(nodes),
        "countries": len([c for c in by_country if c != "XX"]),
        "by_protocol": stats.by_proto,
        "by_country": stats.by_country,
        "best_latency_ms": min(latencies) if latencies else None,
        "median_latency_ms": (
            sorted(latencies)[len(latencies) // 2] if latencies else None
        ),
    }
    (OUTPUT_DIR / "stats.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def interleave(*groups: list[Node]) -> list[Node]:
    """
    Смешивает несколько списков по кругу. Нужно, чтобы в кандидаты на
    проверку попали все протоколы, а не только самый многочисленный.
    """
    buckets: dict[str, list[Node]] = {}
    for group in groups:
        for node in group:
            buckets.setdefault(node.proto, []).append(node)

    order = sorted(buckets, key=lambda p: -len(buckets[p]))
    result: list[Node] = []
    index = 0
    while True:
        added = False
        for proto in order:
            bucket = buckets[proto]
            if index < len(bucket):
                result.append(bucket[index])
                added = True
        if not added:
            return result
        index += 1


def pick_diverse(nodes: list[Node], limit: int, per_country: int) -> list[Node]:
    """
    Отбирает узлы по кругу между странами: сначала по лучшему узлу от каждой
    страны, потом по второму и так далее. Так в списке не окажется двадцати
    серверов из одного датацентра, даже если они самые быстрые.

    per_country — жёсткий потолок на страну. Если из-за него не набирается
    limit, потолок поднимается, пока список не заполнится.
    """
    if limit <= 0 or not nodes:
        return []

    buckets: dict[str, list[Node]] = {}
    for node in nodes:
        buckets.setdefault(node.country or "XX", []).append(node)

    # Страны с самым быстрым узлом идут первыми.
    order = sorted(
        buckets,
        key=lambda code: buckets[code][0].latency_ms
        if buckets[code][0].latency_ms is not None
        else 99999,
    )

    chosen: list[Node] = []
    taken = {code: 0 for code in buckets}
    quota = max(1, per_country)

    while len(chosen) < limit:
        added = False
        for code in order:
            if len(chosen) >= limit:
                break
            index = taken[code]
            if index < len(buckets[code]) and index < quota:
                chosen.append(buckets[code][index])
                taken[code] = index + 1
                added = True
        if not added:
            # Все страны исчерпали квоту. Либо узлы кончились, либо
            # нужно ослабить потолок.
            if all(taken[c] >= len(buckets[c]) for c in buckets):
                break
            quota += max(1, per_country)
    return chosen


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def main() -> int:
    started = time.time()
    stats = Stats()

    log("=== Сбор бесплатных VPN-конфигов ===")

    sources = read_sources()
    stats.sources_total = len(sources)
    if not sources:
        log("[!] Список источников пуст — нечего делать.")
        return 1
    log(f"[1/6] Источников в списке: {len(sources)}")

    # --- Скачивание ---
    payloads: list[str] = []
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        futures = {pool.submit(fetch, url): url for url in sources}
        for fut in as_completed(futures):
            url = futures[fut]
            try:
                data = fut.result()
            except Exception as exc:
                log(f"    [x] {url} -> {type(exc).__name__}")
                data = None
            if data:
                payloads.append(data)
                stats.sources_ok += 1
            else:
                stats.sources_failed.append(url)
    log(f"[2/6] Успешно скачано: {stats.sources_ok}/{stats.sources_total}")

    if not payloads:
        log("[!] Ни один источник не ответил. Прерываюсь, чтобы не затирать "
            "рабочую подписку пустышкой.")
        return 1

    # --- Парсинг и дедупликация ---
    seen: set[str] = set()
    unique: list[Node] = []
    for payload in payloads:
        for link in extract_links(payload):
            stats.links_found += 1
            node = parse_link(link)
            if node is None:
                continue
            stats.parsed += 1
            if node.key in seen:
                continue
            seen.add(node.key)
            unique.append(node)

    stats.unique = len(unique)
    log(f"[3/6] Найдено ссылок: {stats.links_found}, "
        f"валидных: {stats.parsed}, уникальных: {stats.unique}")

    if not unique:
        log("[!] Не удалось извлечь ни одного узла. Подписка не обновлена.")
        return 1

    # --- Быстрый фильтр: TCP-коннект ---
    # QUIC-протоколы TCP-проверку не проходят по своей природе, поэтому
    # отправляем их в sing-box напрямую.
    udp_nodes = [n for n in unique if n.proto in UDP_PROTOCOLS]
    tcp_nodes = [n for n in unique if n.proto not in UDP_PROTOCOLS]

    to_check = tcp_nodes[:CHECK_LIMIT]
    log(f"[4/6] Быстрый фильтр: {len(to_check)} TCP-узлов "
        f"(таймаут {CHECK_TIMEOUT}s)...")
    tcp_alive = check_alive(to_check)

    if udp_nodes:
        alive_udp = check_udp(udp_nodes[:CHECK_LIMIT])
        log(f"      QUIC-узлов с валидным DNS: {len(alive_udp)}")
    else:
        alive_udp = []

    stats.tcp_alive = len(tcp_alive) + len(alive_udp)
    if not tcp_alive and not alive_udp:
        log("[!] Живых узлов не найдено. Подписка не обновлена — "
            "старая версия осталась на месте.")
        return 1

    # --- Настоящая проверка: трафик через sing-box ---
    # Перемешиваем протоколы, чтобы в кандидаты попали не только vless.
    candidates = interleave(tcp_alive, alive_udp)[:VERIFY_CANDIDATES]
    log(f"[5/6] Проверяю реальный доступ в интернет через {len(candidates)} "
        f"узлов...")

    working: list[Node] = []
    for node, latency in probe.verify(candidates, need=MAX_OUTPUT * 3):
        node.latency_ms = latency
        node.verified = True
        working.append(node)

    if working:
        stats.verified = len(working)
        log(f"      Реально работают: {len(working)}")
        selected_pool = working
    else:
        # sing-box недоступен или не собрал ни одного узла — работаем
        # по результатам TCP-проверки, но честно помечаем это в отчёте.
        log("      Настоящая проверка недоступна, откат на TCP-результаты.")
        selected_pool = tcp_alive + alive_udp

    stats.alive = len(selected_pool)

    # --- Страны ---
    log("[6/6] Определяю страны...")
    codes = geo.annotate([n.host for n in selected_pool[:VERIFY_CANDIDATES]])
    for node in selected_pool:
        node.country = codes.get(node.host, "")
    known = sum(1 for n in selected_pool if n.country)
    log(f"      Страна определена у {known}/{len(selected_pool)} узлов")

    # --- Отбор в подписку ---
    selected_pool.sort(
        key=lambda n: (n.latency_ms if n.latency_ms is not None else 99999)
    )
    published = pick_diverse(selected_pool, MAX_OUTPUT, MAX_PER_COUNTRY)

    # --- Запись ---
    report = write_outputs(published, stats)
    log(f"Итог: в подписке {len(published)} узлов из "
        f"{report['countries']} стран")
    log(f"      По протоколам: {report['by_protocol']}")
    log(f"      Задержка: лучшая {report['best_latency_ms']} ms, "
        f"медиана {report['median_latency_ms']} ms")
    log(f"      Проверено через sing-box: "
        f"{'да' if stats.verified else 'нет (TCP-режим)'}")
    log(f"Готово за {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("\nПрервано пользователем.")
        sys.exit(130)
