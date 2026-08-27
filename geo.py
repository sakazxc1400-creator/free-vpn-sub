#!/usr/bin/env python3
"""
Определение страны узла по IP.

Три источника, по порядку:
  1. Локальная база GeoLite2-Country.mmdb, если положить рядом и поставить
     maxminddb.
  2. Публичный batch-API ip-api.com — быстрый, но с лимитами.
  3. CSV-база ip-location-db (скачивается один раз за прогон) — работает
     там, где API недоступен.

Результаты кэшируются в geo_cache.json, поэтому со временем сеть почти
не требуется.
"""

from __future__ import annotations

import bisect
import csv
import gzip
import io
import ipaddress
import json
import socket
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE_FILE = ROOT / "geo_cache.json"
MMDB_FILE = ROOT / "GeoLite2-Country.mmdb"

# ip-api.com: 100 IP за запрос, лимит 15 batch-запросов в минуту.
BATCH_URL = "http://ip-api.com/batch?fields=status,countryCode,query"
BATCH_SIZE = 100
BATCH_PAUSE = 4.5
HTTP_TIMEOUT = 25
DNS_WORKERS = 60
CACHE_TTL_DAYS = 30

# CSV-база: диапазон_начало,диапазон_конец,код_страны. Около 10 МБ.
CSV_URLS = (
    "https://cdn.jsdelivr.net/gh/sapics/ip-location-db@main/"
    "dbip-country/dbip-country-ipv4.csv",
    "https://raw.githubusercontent.com/sapics/ip-location-db/main/"
    "dbip-country/dbip-country-ipv4.csv",
)
CSV_TIMEOUT = 120

# Флаг из кода страны через regional indicator symbols.
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
    """Эмодзи-флаг по двухбуквенному коду страны."""
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
    try:
        age_days = (time.time() - float(saved_at)) / 86400
    except (TypeError, ValueError):
        return {}
    if age_days > CACHE_TTL_DAYS:
        return {}
    return {str(k): str(v) for k, v in entries.items() if isinstance(v, str)}


def save_cache(cache: dict[str, str]) -> None:
    payload = {"saved_at": time.time(), "entries": cache}
    try:
        CACHE_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=0, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        pass


def resolve(host: str) -> str | None:
    """Домен -> IPv4. Если это уже IP, возвращает как есть."""
    try:
        infos = socket.getaddrinfo(host, None, family=socket.AF_INET)
        return infos[0][4][0]
    except (OSError, IndexError):
        return None


def resolve_many(hosts: list[str]) -> dict[str, str]:
    """Параллельный DNS-резолв."""
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
    """Локальная база MaxMind, если доступна."""
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
    """Batch-запросы к ip-api.com."""
    result: dict[str, str] = {}
    for start in range(0, len(ips), BATCH_SIZE):
        chunk = ips[start:start + BATCH_SIZE]
        body = json.dumps(chunk).encode("utf-8")
        req = urllib.request.Request(
            BATCH_URL,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "geo/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                payload = json.loads(resp.read().decode("utf-8", "ignore"))
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


# Кэш CSV-таблицы на время одного прогона: (начала, концы, коды).
_csv_table: tuple[list[int], list[int], list[str]] | None = None
_csv_tried = False


def _load_csv_table() -> tuple[list[int], list[int], list[str]] | None:
    """Скачивает и разбирает CSV-базу диапазонов. Один раз за прогон."""
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
                data = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
                raw = data
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
    """Поиск по CSV-базе диапазонов (бинарный поиск)."""
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
        # Диапазоны не покрывают всё адресное пространство, поэтому
        # обязательно проверяем верхнюю границу найденного диапазона.
        if 0 <= index < len(codes) and value <= ends[index]:
            result[ip] = codes[index]
    return result


def annotate(hosts: list[str]) -> dict[str, str]:
    """
    host -> код страны. Хосты без определённой страны в результат не попадают.
    Кэш переиспользуется между прогонами.
    """
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

    # Всё, что не определилось через API, ищем в CSV-базе.
    missing = [ip for ip in ips if ip not in ip_to_code]
    if missing:
        ip_to_code.update(lookup_csv(missing))

    for host, ip in host_to_ip.items():
        code = ip_to_code.get(ip)
        if code:
            known[host] = code
            cache[host] = code

    save_cache(cache)
    return known
