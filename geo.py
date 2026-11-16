#!/usr/bin/env python3
"""Определение страны по IP через mmdb, ip-api.com и CSV-базу."""

from __future__ import annotations

import bisect
import csv
import gzip
import io
import ipaddress
import json
import re
import socket
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE_FILE = ROOT / "geo_cache.json"
MMDB_FILE = ROOT / "GeoLite2-Country.mmdb"

# ip-api: 100 IP за запрос, 15 запросов в минуту
BATCH_URL = "http://ip-api.com/batch?fields=status,countryCode,query"
BATCH_SIZE = 100
BATCH_PAUSE = 4.5
HTTP_TIMEOUT = 25
DNS_WORKERS = 60
CACHE_TTL_DAYS = 30

# CSV-база: начало,конец,код страны, около 10 МБ
CSV_URLS = (
    "https://cdn.jsdelivr.net/gh/sapics/ip-location-db@main/"
    "dbip-country/dbip-country-ipv4.csv",
    "https://raw.githubusercontent.com/sapics/ip-location-db/main/"
    "dbip-country/dbip-country-ipv4.csv",
)
MAX_CSV_BYTES = 24 * 1024 * 1024
CSV_TIMEOUT = 120

_FLAG_OFFSET = 0x1F1E6 - ord("A")

COUNTRY_NAMES = {
    "AE": "ОАЭ", "AL": "Албания", "AM": "Армения", "AR": "Аргентина",
    "AT": "Австрия", "AU": "Австралия", "AZ": "Азербайджан", "BE": "Бельгия",
    "BG": "Болгария", "BH": "Бахрейн", "BR": "Бразилия", "BY": "Беларусь",
    "CA": "Канада", "CH": "Швейцария", "CL": "Чили", "CN": "Китай",
    "CO": "Колумбия", "CR": "Коста-Рика", "CY": "Кипр", "CZ": "Чехия",
    "DE": "Германия", "DK": "Дания", "EC": "Эквадор", "EE": "Эстония",
    "EG": "Египет", "ES": "Испания", "FI": "Финляндия", "FR": "Франция",
    "GB": "Британия", "GE": "Грузия", "GR": "Греция", "HK": "Гонконг",
    "HR": "Хорватия", "HU": "Венгрия", "ID": "Индонезия", "IE": "Ирландия",
    "IL": "Израиль", "IN": "Индия", "IQ": "Ирак", "IR": "Иран",
    "IS": "Исландия", "IT": "Италия", "JP": "Япония", "KE": "Кения",
    "KG": "Кыргызстан", "KH": "Камбоджа", "KR": "Корея", "KZ": "Казахстан",
    "LT": "Литва", "LU": "Люксембург", "LV": "Латвия", "MD": "Молдова",
    "MX": "Мексика", "MY": "Малайзия", "NG": "Нигерия", "NL": "Нидерланды",
    "NO": "Норвегия", "NZ": "Новая Зеландия", "PA": "Панама", "PE": "Перу",
    "PH": "Филиппины", "PK": "Пакистан", "PL": "Польша", "PT": "Португалия",
    "QA": "Катар", "RO": "Румыния", "RS": "Сербия", "RU": "Россия",
    "SA": "Саудовская Аравия", "SC": "Сейшелы", "SE": "Швеция",
    "SG": "Сингапур", "SI": "Словения", "SK": "Словакия", "TH": "Таиланд",
    "TR": "Турция", "TW": "Тайвань", "UA": "Украина", "US": "США",
    "UZ": "Узбекистан", "VN": "Вьетнам", "ZA": "ЮАР",
}


def flag(code: str) -> str:
    code = (code or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        return "🏴"
    return "".join(chr(ord(ch) + _FLAG_OFFSET) for ch in code)


def country_name(code: str) -> str:
    code = (code or "").strip().upper()
    return COUNTRY_NAMES.get(code, code or "??")


def load_cache() -> dict[str, str]:
    if not CACHE_FILE.exists():
        return {}
    try:
        raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}

    entries = raw.get("entries")
    if not isinstance(entries, dict):
        return {}
    saved_at = raw.get("saved_at", 0)
    stamps = raw.get("updated_at", {})
    if not isinstance(stamps, dict):
        stamps = {}
    result = {}
    now = time.time()
    for host, code in entries.items():
        if not isinstance(code, str) or not re.fullmatch(r"[A-Z]{2}", code):
            continue
        try:
            updated = float(stamps.get(host, saved_at))
        except (TypeError, ValueError, OverflowError):
            continue
        age_days = (now - updated) / 86400
        if 0 <= age_days <= CACHE_TTL_DAYS:
            result[str(host)] = code
    return result


def save_cache(cache: dict[str, str], refreshed: set[str] | None = None) -> None:
    previous_stamps = {}
    try:
        previous = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if isinstance(previous.get("updated_at"), dict):
            previous_stamps = previous["updated_at"]
    except (OSError, ValueError, AttributeError):
        pass
    now = time.time()
    refreshed = set(cache) if refreshed is None else refreshed
    stamps = {host: (now if host in refreshed else previous_stamps.get(host, now))
              for host in cache}
    payload = {"saved_at": now, "updated_at": stamps, "entries": cache}
    try:
        CACHE_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=0, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        pass


def read_limited_response(response, limit: int) -> bytes | None:
    """Read compressed or plain HTTP content without unbounded allocation."""
    encoding = response.headers.get("Content-Encoding", "").lower()
    raw = response.read(limit + 1)
    if encoding == "gzip":
        if len(raw) > limit:
            return None
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as archive:
                raw = archive.read(limit + 1)
        except (OSError, EOFError):
            return None
    elif encoding:
        return None
    return raw if len(raw) <= limit else None


def resolve(host: str) -> str | None:
    """Домен -> IPv4; готовый IP возвращает как есть."""
    try:
        infos = socket.getaddrinfo(host, None, family=socket.AF_INET)
        return infos[0][4][0]
    except (OSError, IndexError):
        return None


def resolve_many(hosts: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=DNS_WORKERS) as pool:
        futures = {pool.submit(resolve, h): h for h in hosts}
        for fut in as_completed(futures):
            host = futures[fut]
            try:
                ip = fut.result()
            except Exception:
                ip = None
            if ip:
                mapping[host] = ip
    return mapping


def lookup_mmdb(ips: list[str]) -> dict[str, str]:
    if not MMDB_FILE.exists():
        return {}
    try:
        import maxminddb
    except ImportError:
        return {}

    result: dict[str, str] = {}
    try:
        with maxminddb.open_database(str(MMDB_FILE)) as reader:
            for ip in ips:
                try:
                    record = reader.get(ip)
                except (ValueError, OSError):
                    continue
                if isinstance(record, dict):
                    code = (record.get("country") or {}).get("iso_code")
                    if code:
                        result[ip] = str(code).upper()
    except (OSError, ValueError):
        return result
    return result


def lookup_api(ips: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for start in range(0, len(ips), BATCH_SIZE):
        chunk = ips[start:start + BATCH_SIZE]
        body = json.dumps(chunk).encode("utf-8")
        if len(body) > MAX_CSV_BYTES:
            continue
        req = urllib.request.Request(
            BATCH_URL,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "geo/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                raw = resp.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    continue
                payload = json.loads(raw.decode("utf-8", "ignore"))
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                json.JSONDecodeError, ValueError, TimeoutError):
            continue

        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            if item.get("status") == "success":
                ip = str(item.get("query", ""))
                code = str(item.get("countryCode", "")).upper()
                if ip and len(code) == 2:
                    result[ip] = code

        if start + BATCH_SIZE < len(ips):
            time.sleep(BATCH_PAUSE)
    return result


# кэш таблицы на прогон: (начала, концы, коды)
_csv_table: tuple[list[int], list[int], list[str]] | None = None
_csv_tried = False


def _load_csv_table() -> tuple[list[int], list[int], list[str]] | None:
    global _csv_table, _csv_tried
    if _csv_table is not None or _csv_tried:
        return _csv_table
    _csv_tried = True

    raw: bytes | None = None
    for url in CSV_URLS:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "geo/1.0", "Accept-Encoding": "gzip"}
            )
            with urllib.request.urlopen(req, timeout=CSV_TIMEOUT) as resp:
                raw = read_limited_response(resp, MAX_CSV_BYTES)
                if raw is None:
                    continue
            break
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                TimeoutError, gzip.BadGzipFile, EOFError):
            continue

    if not raw:
        return None

    starts: list[int] = []
    ends: list[int] = []
    codes: list[str] = []
    try:
        text = io.StringIO(raw.decode("utf-8", "ignore"))
        for row in csv.reader(text):
            if len(row) < 3:
                continue
            code = row[2].strip().upper()
            if len(code) != 2:
                continue
            try:
                start_ip = int(ipaddress.IPv4Address(row[0].strip()))
                end_ip = int(ipaddress.IPv4Address(row[1].strip()))
            except (ipaddress.AddressValueError, ValueError):
                continue
            starts.append(start_ip)
            ends.append(end_ip)
            codes.append(code)
    except (UnicodeDecodeError, csv.Error, ValueError):
        return None

    if not starts:
        return None

    _csv_table = (starts, ends, codes)
    return _csv_table


def lookup_csv(ips: list[str]) -> dict[str, str]:
    table = _load_csv_table()
    if table is None:
        return {}
    starts, ends, codes = table

    result: dict[str, str] = {}
    for ip in ips:
        try:
            value = int(ipaddress.IPv4Address(ip))
        except (ipaddress.AddressValueError, ValueError):
            continue
        index = bisect.bisect_right(starts, value) - 1
        # проверяем верхнюю границу: между диапазонами бывают дыры
        if 0 <= index < len(codes) and value <= ends[index]:
            result[ip] = codes[index]
    return result


def annotate(hosts: list[str]) -> dict[str, str]:
    """host -> код страны, кэш переиспользуется между прогонами."""
    unique = sorted({h.strip().lower() for h in hosts if h.strip()})
    if not unique:
        return {}

    cache = load_cache()
    known = {h: cache[h] for h in unique if h in cache}
    unknown = [h for h in unique if h not in cache]
    if not unknown:
        return known

    host_to_ip = resolve_many(unknown)
    ips = sorted(set(host_to_ip.values()))
    if not ips:
        return known

    ip_to_code = lookup_mmdb(ips)

    missing = [ip for ip in ips if ip not in ip_to_code]
    if missing:
        ip_to_code.update(lookup_api(missing))

    missing = [ip for ip in ips if ip not in ip_to_code]
    if missing:
        ip_to_code.update(lookup_csv(missing))

    resolved_hosts = set()
    for host, ip in host_to_ip.items():
        code = ip_to_code.get(ip)
        if code:
            known[host] = code
            cache[host] = code
            resolved_hosts.add(host)

    save_cache(cache, refreshed=resolved_hosts)
    return known
