#!/usr/bin/env python3
"""
Агрегатор бесплатных VPN-подписок.

Что делает:
  1. Скачивает конфиги из списка источников (sources.txt).
  2. Понимает форматы: plain-text и base64.
  3. Извлекает ссылки протоколов vless/vmess/trojan/ss/hysteria2/tuic.
  4. Убирает дубликаты по реальному адресу сервера (а не по тексту ссылки).
  5. Проверяет доступность TCP-портов и отбрасывает мёртвые узлы.
  6. Складывает всё в единую подписку output/sub.txt (base64) + вспомогательные файлы.

Зависимостей нет — только стандартная библиотека Python 3.9+.
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
CHECK_LIMIT = 6000          # максимум узлов, отправляемых на проверку
MAX_OUTPUT = 1500           # максимум узлов в итоговой подписке

USER_AGENT = "Mozilla/5.0 (compatible; free-vpn-sub/1.0; +https://github.com)"

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
    alive: int = 0
    by_proto: dict[str, int] = field(default_factory=dict)


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


def fetch(url: str) -> str | None:
    """Скачивает URL с retry и экспоненциальной паузой."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout,
                ConnectionError, TimeoutError, OSError) as exc:
            if attempt == FETCH_RETRIES:
                log(f"    [x] {url} -> {type(exc).__name__}: {exc}")
                return None
            time.sleep(1.5 * attempt)
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
    except Exception as exc:  # защита от любого мусора во входных данных
        log(f"    [~] не разобрал ссылку ({type(exc).__name__})")
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
    """Заменяет комментарий ссылки на понятную метку с задержкой."""
    label = f"[{index:03d}] {node.proto} {node.host} {node.latency_ms}ms"
    tag = urllib.parse.quote(label, safe="[]")
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

    # Разбивка по протоколам.
    by_proto: dict[str, list[str]] = {}
    for node, line in zip(nodes, tagged):
        by_proto.setdefault(node.proto, []).append(line)
    for proto, lines in by_proto.items():
        (OUTPUT_DIR / f"{proto}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    stats.by_proto = {p: len(v) for p, v in sorted(by_proto.items())}

    # Отчёт для README и для отладки.
    report = {
        "updated": updated,
        "sources_total": stats.sources_total,
        "sources_ok": stats.sources_ok,
        "sources_failed": stats.sources_failed,
        "links_found": stats.links_found,
        "parsed": stats.parsed,
        "unique": stats.unique,
        "alive": stats.alive,
        "published": len(nodes),
        "by_protocol": stats.by_proto,
        "best_latency_ms": nodes[0].latency_ms if nodes else None,
    }
    (OUTPUT_DIR / "stats.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


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
    log(f"[1/5] Источников в списке: {len(sources)}")

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
    log(f"[2/5] Успешно скачано: {stats.sources_ok}/{stats.sources_total}")

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
    log(f"[3/5] Найдено ссылок: {stats.links_found}, "
        f"валидных: {stats.parsed}, уникальных: {stats.unique}")

    if not unique:
        log("[!] Не удалось извлечь ни одного узла. Подписка не обновлена.")
        return 1

    # --- Проверка живости ---
    to_check = unique[:CHECK_LIMIT]
    log(f"[4/5] Проверяю доступность {len(to_check)} узлов "
        f"(таймаут {CHECK_TIMEOUT}s)...")
    alive = check_alive(to_check)
    stats.alive = len(alive)

    if not alive:
        log("[!] Живых узлов не найдено. Подписка не обновлена — "
            "старая версия осталась на месте.")
        return 1

    published = alive[:MAX_OUTPUT]

    # --- Запись ---
    report = write_outputs(published, stats)
    log(f"[5/5] Живых узлов: {stats.alive}, в подписке: {len(published)}")
    log(f"      По протоколам: {report['by_protocol']}")
    log(f"      Лучшая задержка: {report['best_latency_ms']} ms")
    log(f"Готово за {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("\nПрервано пользователем.")
        sys.exit(130)
