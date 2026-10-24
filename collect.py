#!/usr/bin/env python3
"""Сбор бесплатных VPN-подписок: источники из sources.txt, результат в output/."""

from __future__ import annotations

import base64
import binascii
import ipaddress
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import geo
import probe

ROOT = Path(__file__).resolve().parent
SOURCES_FILE = ROOT / "sources.txt"
OUTPUT_DIR = ROOT / "output"

PROTOCOLS = ("vless", "vmess", "trojan", "ss", "hysteria2", "hy2", "tuic")

LINK_RE = re.compile(
    r"\b(?:" + "|".join(PROTOCOLS) + r")://[^\s\"'<>\\]+",
    re.IGNORECASE,
)

FETCH_TIMEOUT = 25
FETCH_RETRIES = 3
FETCH_WORKERS = 12

CHECK_TIMEOUT = 3.0
CHECK_WORKERS = 300
CHECK_LIMIT = 20000

# sub.txt короткая и быстрая, sub-full.txt это всё, что прошло проверку
MAX_OUTPUT = 200
MAX_FULL = 5000

# с запасом: рабочих узлов обычно 5-15%
VERIFY_CANDIDATES = 12000

# работают поверх UDP, TCP-коннект их не проверяет
UDP_PROTOCOLS = frozenset({"hysteria2", "tuic"})

MAX_PER_COUNTRY = 12

# между прогонами копим стаж узлов
HISTORY_FILE = OUTPUT_DIR / "history.json"
STABLE_RUNS = 6             # столько замеров подряд нужен для стабильной
HISTORY_KEEP_HOURS = 48     # сколько помним выпавшие из сборки узлы
HISTORY_GAP_HOURS = 8       # пауза больше этого обнуляет стаж
HISTORY_VERSION = 2         # 2: стаж в часах, а не в прогонах

# блокируем публикацию, только если узлов и стало меньше прошлого раза, и вообще мало
MIN_KEEP_RATIO = 0.6
MIN_KEEP_ABS = 400

USER_AGENT = "Mozilla/5.0 (compatible; free-vpn-sub/1.0; +https://github.com)"

# зеркала для заблокированного raw.githubusercontent.com
RAW_HOST = "raw.githubusercontent.com"
MIRROR_TEMPLATES = (
    "https://gh-proxy.com/https://{raw}",
    "https://raw.gitcode.host/{path}",
)

VALID_PORT_RANGE = range(1, 65536)


@dataclass
class Node:
    raw: str
    proto: str
    host: str
    port: int
    ident: str                     # ключ дедупликации
    latency_ms: int | None = None
    country: str = ""
    verified: bool = False
    tls_ok: bool = True            # HTTPS с проверкой сертификата
    speed_mbps: float | None = None
    streak: int = 0
    uptime_hours: float = 0.0

    @property
    def key(self) -> str:
        return self.ident

    @property
    def addr(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass
class Stats:
    sources_total: int = 0
    sources_ok: int = 0
    sources_failed: list[str] = field(default_factory=list)
    links_found: int = 0
    parsed: int = 0
    unique: int = 0
    tcp_alive: int = 0
    verified: int = 0
    alive: int = 0
    servers: int = 0
    tls_ok: int = 0
    stable: int = 0
    speed_measured: int = 0
    by_proto: dict[str, int] = field(default_factory=dict)
    by_country: dict[str, int] = field(default_factory=dict)


def log(msg: str) -> None:
    print(msg, flush=True)


def b64_decode_loose(data: str) -> str | None:
    """base64 без padding и url-safe; None, если это не base64."""
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
    """Нижний регистр, без скобок IPv6."""
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
        return bool(re.fullmatch(r"[a-z0-9._-]+\.[a-z]{2,}", host))
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def read_sources() -> list[str]:
    if not SOURCES_FILE.exists():
        log(f"[!] Нет файла {SOURCES_FILE.name}")
        return []
    urls: list[str] = []
    for line in SOURCES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return list(dict.fromkeys(urls))


def mirror_urls(url: str) -> list[str]:
    """Для raw.githubusercontent.com добавляет зеркала."""
    if RAW_HOST not in url:
        return [url]
    raw = url.split("://", 1)[-1]
    path = raw[len(RAW_HOST) + 1:] if raw.startswith(RAW_HOST + "/") else raw
    variants = [url]
    for template in MIRROR_TEMPLATES:
        variants.append(template.format(raw=raw, path=path))
    return variants


def fetch(url: str) -> str | None:
    """Скачивает URL; если не вышло, пробует зеркала."""
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
    """Ссылки из текста, при неудаче из base64."""
    links = LINK_RE.findall(payload)
    if links:
        return links
    decoded = b64_decode_loose(payload)
    if decoded:
        return LINK_RE.findall(decoded)
    return []


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
    """ss:// в двух вариантах: userinfo в base64 или вся ссылка целиком."""
    body = link[len("ss://"):]
    body = body.split("#", 1)[0]
    body = body.split("?", 1)[0]

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
    """Разбирает host:port и [ipv6]:port."""
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
    """Разбор vless/trojan/hysteria2/tuic: proto://user@host:port?params#remark."""
    try:
        parsed = urllib.parse.urlsplit(link)
    except ValueError:
        return None

    host = normalize_host(parsed.hostname or "")
    port = parsed.port
    if port is None:
        return None
    if not host or port not in VALID_PORT_RANGE or not is_routable(host):
        return None

    user = (parsed.username or "").strip().lower()
    if proto in ("vless", "trojan") and not user:
        return None

    # sni входит в ident
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
    """Ссылка -> узел, или None. Исключений не бросает."""
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
        return None
    return None


def tcp_ping(node: Node) -> tuple[Node, int | None]:
    start = time.perf_counter()
    try:
        with socket.create_connection((node.host, node.port), timeout=CHECK_TIMEOUT):
            elapsed = int((time.perf_counter() - start) * 1000)
            return node, elapsed
    except (OSError, socket.timeout, ValueError):
        return node, None


def dns_ok(node: Node) -> tuple[Node, bool]:
    """Для UDP-узлов проверяем хотя бы DNS."""
    try:
        socket.getaddrinfo(node.host, node.port, proto=socket.IPPROTO_UDP)
        return node, True
    except (OSError, socket.gaierror, ValueError):
        return node, False


def check_udp(nodes: list[Node]) -> list[Node]:
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


def parse_stamp(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def load_history() -> dict:
    empty = {"v": HISTORY_VERSION, "nodes": {}}
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), dict):
        return empty
    if data.get("v") != HISTORY_VERSION:
        # старый формат считал стаж в прогонах, а прогоны идут неравномерно
        return empty
    return data


def apply_history(history: dict, nodes: list[Node], now: datetime) -> None:
    """Считает стаж узлов и обновляет историю."""
    stored: dict = history.setdefault("nodes", {})
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    tolerance = timedelta(hours=HISTORY_GAP_HOURS)
    alive: set[str] = set()

    for node in nodes:
        key = node.addr
        alive.add(key)
        prev = stored.get(key) or {}
        prev_stamp = parse_stamp(str(prev.get("last", "")))
        if prev_stamp is not None and now - prev_stamp <= tolerance:
            streak = int(prev.get("streak", 0)) + 1
            first = prev.get("first") or stamp
        else:
            streak = 1
            first = stamp

        node.streak = streak
        started = parse_stamp(str(first))
        hours = (now - started).total_seconds() / 3600 if started else 0.0
        node.uptime_hours = round(hours, 1)
        stored[key] = {
            "streak": streak,
            "first": first,
            "last": stamp,
            "runs": int(prev.get("runs", 0)) + 1,
        }

    # выпавшие узлы теряют стаж, но запись живёт ещё HISTORY_KEEP_HOURS
    cutoff = now - timedelta(hours=HISTORY_KEEP_HOURS)
    for key in list(stored):
        if key in alive:
            continue
        entry = stored.get(key) or {}
        last = parse_stamp(str(entry.get("last", "")))
        if last is None or last < cutoff:
            del stored[key]
            continue
        if entry.get("streak"):
            entry["streak"] = 0

    history["updated"] = stamp
    history["count"] = len(stored)


def save_history(history: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def pick_stable(nodes: list[Node]) -> list[Node]:
    return [n for n in nodes if n.streak >= STABLE_RUNS]


def previous_report() -> dict | None:
    try:
        data = json.loads((OUTPUT_DIR / "stats.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def shrink_guard_blocks(prev_full, count: int, allow: bool = False) -> bool:
    """Не публиковать ли сборку: резкий провал по числу узлов."""
    if allow:
        return False
    if not isinstance(prev_full, int) or prev_full <= 100:
        return False
    return count < prev_full * MIN_KEEP_RATIO and count < MIN_KEEP_ABS


def retag(node: Node, index: int) -> str:
    """Название узла: страна, протокол, задержка, стаж."""
    parts: list[str] = []
    if node.country:
        parts.append(f"{geo.flag(node.country)} {geo.country_name(node.country)}")
    else:
        parts.append("🏴 ??")
    parts.append(node.proto)
    if node.latency_ms is not None:
        parts.append(f"{node.latency_ms}ms")
    if node.uptime_hours >= 1:
        parts.append(f"{node.uptime_hours:.0f}ч")
    if not node.tls_ok:
        # сертификат не проверился, узел может подменять TLS
        parts.append("⚠")

    label = f"{index:02d}. " + " · ".join(parts)
    tag = urllib.parse.quote(label, safe="")
    base = node.raw.split("#", 1)[0]
    return f"{base}#{tag}"


def write_outputs(nodes: list[Node], full: list[Node], stats: Stats,
                  stable: list[Node] | None = None) -> dict:
    """Пишет sub.txt, sub-full.txt, sub-stable.txt и разбивки в output/."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    tagged = [retag(n, i + 1) for i, n in enumerate(nodes)]
    plain = "\n".join(tagged)

    # в sub.txt base64, в all.txt тот же список текстом
    (OUTPUT_DIR / "sub.txt").write_text(
        base64.b64encode(plain.encode("utf-8")).decode("ascii"),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "all.txt").write_text(plain + "\n", encoding="utf-8")

    full_tagged = [retag(n, i + 1) for i, n in enumerate(full)]
    full_plain = "\n".join(full_tagged)
    (OUTPUT_DIR / "sub-full.txt").write_text(
        base64.b64encode(full_plain.encode("utf-8")).decode("ascii"),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "all-full.txt").write_text(full_plain + "\n", encoding="utf-8")

    # пишем всегда, даже пустыми: иначе клиент получит 404
    stable = stable or []
    stable_tagged = [retag(n, i + 1) for i, n in enumerate(stable)]
    stable_plain = "\n".join(stable_tagged)
    (OUTPUT_DIR / "sub-stable.txt").write_text(
        base64.b64encode(stable_plain.encode("utf-8")).decode("ascii"),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "all-stable.txt").write_text(
        stable_plain + "\n", encoding="utf-8"
    )

    nodes_json = [
        {
            "i": index + 1,
            "cc": n.country,
            "name": geo.country_name(n.country) if n.country else "?",
            "proto": n.proto,
            "ms": n.latency_ms,
            "mbps": n.speed_mbps,
            "up": n.uptime_hours,
            "tls": bool(n.tls_ok),
            "addr": n.addr,
            "url": retag(n, index + 1),
        }
        for index, n in enumerate(nodes)
    ]
    (OUTPUT_DIR / "nodes.json").write_text(
        json.dumps(nodes_json, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    # старые файлы удаляем, чтобы не остались от прошлого прогона
    known_protos = {"vless", "vmess", "trojan", "ss", "hysteria2", "tuic"}
    for proto in known_protos:
        stale = OUTPUT_DIR / f"{proto}.txt"
        if stale.exists():
            stale.unlink()

    by_proto: dict[str, list[str]] = {}
    for node, line in zip(full, full_tagged):
        by_proto.setdefault(node.proto, []).append(line)
    for proto, lines in by_proto.items():
        (OUTPUT_DIR / f"{proto}.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
    stats.by_proto = {p: len(v) for p, v in sorted(by_proto.items())}

    country_dir = OUTPUT_DIR / "by-country"
    country_dir.mkdir(exist_ok=True)
    for stale in country_dir.glob("*.txt"):
        stale.unlink()

    by_country: dict[str, list[str]] = {}
    for node, line in zip(full, full_tagged):
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

    latencies = [n.latency_ms for n in full if n.latency_ms is not None]
    speeds = sorted(n.speed_mbps for n in full if n.speed_mbps is not None)

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
        "servers": stats.servers,
        "tls_ok": stats.tls_ok,
        "speed_measured": stats.speed_measured,
        "stable": len(stable),
        "stable_runs": STABLE_RUNS,
        "published": len(nodes),
        "published_full": len(full),
        "countries": len([c for c in by_country if c != "XX"]),
        "by_protocol": stats.by_proto,
        "by_country": stats.by_country,
        "best_latency_ms": min(latencies) if latencies else None,
        "median_latency_ms": (
            sorted(latencies)[len(latencies) // 2] if latencies else None
        ),
        "best_speed_mbps": speeds[-1] if speeds else None,
        "median_speed_mbps": speeds[len(speeds) // 2] if speeds else None,
    }
    (OUTPUT_DIR / "stats.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def write_clash(nodes: list[Node]) -> int:
    """Пишет output/clash.yaml; если конвертер упал, сборка идёт дальше."""
    try:
        import clashout
    except ImportError:
        log("      clashout.py не найден: Clash-подписка пропущена")
        return 0

    labels = [
        urllib.parse.unquote(retag(n, i + 1).split("#", 1)[1])
        for i, n in enumerate(nodes)
    ]
    try:
        text = clashout.build_clash(nodes, labels=labels)
    except Exception as exc:
        log(f"      Clash-подписка не собралась: {type(exc).__name__}: {exc}")
        return 0

    (OUTPUT_DIR / "clash.yaml").write_text(text, encoding="utf-8")
    return len(nodes)


def interleave(*groups: list[Node]) -> list[Node]:
    """Смешивает списки по кругу, чтобы попали все протоколы."""
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


def dedupe_servers(nodes: list[Node]) -> list[Node]:
    """По одному узлу на адрес сервера, остаётся самый быстрый."""
    best: dict[tuple[str, int], Node] = {}
    for node in nodes:
        key = (node.host, node.port)
        current = best.get(key)
        if current is None:
            best[key] = node
            continue
        current_ms = current.latency_ms if current.latency_ms is not None else 99999
        node_ms = node.latency_ms if node.latency_ms is not None else 99999
        if node_ms < current_ms:
            best[key] = node
    return list(best.values())


def pick_diverse(nodes: list[Node], limit: int, per_country: int) -> list[Node]:
    """По одному узлу от каждой страны по кругу, с потолком на страну."""
    if limit <= 0 or not nodes:
        return []

    buckets: dict[str, list[Node]] = {}
    for node in nodes:
        buckets.setdefault(node.country or "XX", []).append(node)

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
            if all(taken[c] >= len(buckets[c]) for c in buckets):
                break
            quota += max(1, per_country)
    return chosen


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

    candidates = interleave(tcp_alive, alive_udp)[:VERIFY_CANDIDATES]
    log(f"[5/6] Проверяю реальный доступ в интернет через {len(candidates)} "
        f"узлов...")

    working: list[Node] = []
    for node, latency in probe.verify(candidates, need=MAX_FULL):
        node.latency_ms = latency
        node.verified = True
        working.append(node)

    if working:
        stats.verified = len(working)
        log(f"      Реально работают: {len(working)}")
        selected_pool = working
    else:
        log("      Настоящая проверка недоступна, откат на TCP-результаты.")
        selected_pool = tcp_alive + alive_udp

    stats.alive = len(selected_pool)

    servers = dedupe_servers(selected_pool)
    stats.servers = len(servers)
    if len(servers) < len(selected_pool):
        log(f"      Уникальных адресов: {len(servers)} "
            f"(из {len(selected_pool)} рабочих конфигов)")
    stats.tls_ok = sum(1 for n in servers if n.tls_ok)
    if stats.tls_ok < len(servers):
        log(f"      HTTPS с проверкой сертификата прошли {stats.tls_ok} "
            f"из {len(servers)}: остальные могут подменять TLS и попадут "
            f"только в полную подписку")
    selected_pool = servers

    now = datetime.now(timezone.utc)
    history = load_history()
    apply_history(history, selected_pool, now)
    veterans = sum(1 for n in selected_pool if n.streak >= STABLE_RUNS)
    log(f"      Держатся {STABLE_RUNS}+ прогонов подряд: {veterans}")

    log("[6/6] Определяю страны...")
    codes = geo.annotate([n.host for n in selected_pool[:VERIFY_CANDIDATES]])
    for node in selected_pool:
        node.country = codes.get(node.host, "")
    known = sum(1 for n in selected_pool if n.country)
    log(f"      Страна определена у {known}/{len(selected_pool)} узлов")

    def rank(node: Node) -> tuple:
        """Порядок в подписке: сертификат, скорость, задержка."""
        return (
            0 if node.tls_ok else 1,
            0 if node.speed_mbps is not None else 1,
            -(node.speed_mbps or 0.0),
            node.latency_ms if node.latency_ms is not None else 99999,
        )

    selected_pool.sort(key=rank)
    full = selected_pool[:MAX_FULL]
    # короткий список с разбросом по странам
    published = pick_diverse(full, MAX_OUTPUT, MAX_PER_COUNTRY)

    # меряем тех, кто попал в основную подписку
    if published:
        stats.speed_measured = probe.measure_speed(published)
        published.sort(key=rank)

    # стабильные: держатся уже несколько часов
    stable = pick_diverse(pick_stable(full), MAX_OUTPUT, MAX_PER_COUNTRY)
    stats.stable = len(stable)

    prev_full = (previous_report() or {}).get("published_full")
    if shrink_guard_blocks(prev_full, len(full),
                           allow=bool(os.environ.get("ALLOW_SHRINK"))):
        log(f"[!] Рабочих узлов {len(full)}, а в прошлый раз было {prev_full}. "
            f"Это меньше {int(MIN_KEEP_RATIO * 100)}% от прошлого прогона, "
            f"да и вообще меньше {MIN_KEEP_ABS}.")
        log("[!] Публиковать это не буду, прошлая подписка остаётся на месте. "
            "Если уменьшение ожидаемое, запусти с ALLOW_SHRINK=1.")
        return 1

    report = write_outputs(published, full, stats, stable)
    save_history(history)
    clash_count = write_clash(published)
    if clash_count:
        log(f"      Clash-подписка: {clash_count} узлов")

    log(f"Итог: в основной подписке {len(published)} узлов, "
        f"в полной {len(full)} из {report['countries']} стран, "
        f"в стабильной {len(stable)}")
    log(f"      По протоколам: {report['by_protocol']}")
    log(f"      Задержка: лучшая {report['best_latency_ms']} ms, "
        f"медиана {report['median_latency_ms']} ms")
    if report.get("best_speed_mbps"):
        log(f"      Скорость: лучшая {report['best_speed_mbps']} Мбит/с, "
            f"медиана {report['median_speed_mbps']} Мбит/с")
    log(f"      Проверено через sing-box: "
        f"{'да' if stats.verified else 'нет (TCP-режим)'}")
    log(f"Готово за {time.time() - started:.1f}s")

    try:
        import notify
        if notify.send_report(report):
            log("      Сводка отправлена в Telegram")
        else:
            log("      Сводка в Telegram не ушла: нет секретов или Telegram недоступен")
    except Exception as exc:
        log(f"      Уведомление не отправлено: {type(exc).__name__}")

    return 0


if __name__ == "__main__":
    code = 0
    try:
        code = main()
    except KeyboardInterrupt:
        log("\nПрервано пользователем.")
        code = 130
    if code != 0:
        # о падении сообщаем сразу
        try:
            import notify
            if not notify.send_failure(f"Сборка подписки упала, код {code}"):
                log("Уведомление о сбое не ушло: нет секретов или "
                    "Telegram недоступен.")
        except Exception:
            pass
    sys.exit(code)
