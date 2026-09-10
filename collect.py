import os
import re
import json
import base64
import socket
from urllib.parse import urlparse, quote, unquote
from datetime import datetime, timezone
import requests

SOURCES_FILE = "sources.txt"
OUTPUT_DIR = "output"
CACHE_FILE = "geo_cache.json"

SUPPORTED_PROTOCOLS = {"vless", "vmess", "ss", "trojan", "hysteria2", "hy2", "tuic"}
GEO_CACHE = {}


def load_geo_cache():
    global GEO_CACHE
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                GEO_CACHE = json.load(f)
        except Exception:
            GEO_CACHE = {}


def save_geo_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(GEO_CACHE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения {CACHE_FILE}: {e}")


def safe_b64decode(s: str) -> str:
    s = s.strip()
    s += "=" * (-len(s) % 4)
    try:
        return base64.b64decode(s).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def resolve_ip(host: str) -> str | None:
    try:
        return socket.gethostbyname(host)
    except Exception:
        return None


def get_country_code(host: str) -> str:
    if not host:
        return "UN"
    
    ip = resolve_ip(host) if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host) else host
    if not ip:
        return "UN"

    if ip in GEO_CACHE:
        return GEO_CACHE[ip]

    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}?fields=status,countryCode", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                code = data.get("countryCode", "UN").upper()
                GEO_CACHE[ip] = code
                return code
    except Exception:
        pass

    GEO_CACHE[ip] = "UN"
    return "UN"


def extract_node_identity(link: str) -> tuple | None:
    """Извлекает уникальный ключ для дедупликации."""
    try:
        if "://" not in link:
            return None
        scheme, rest = link.split("://", 1)
        scheme = scheme.lower()
        if scheme == "hy2":
            scheme = "hysteria2"

        if scheme not in SUPPORTED_PROTOCOLS:
            return None

        if scheme == "vmess":
            b64_part = rest.split("#", 1)[0].split("?", 1)[0]
            raw_json = safe_b64decode(b64_part)
            if not raw_json:
                return None
            data = json.loads(raw_json)
            add = str(data.get("add", "")).lower().strip()
            port = int(data.get("port", 0))
            uuid = str(data.get("id", "")).strip()
            return ("vmess", add, port, uuid)

        if scheme == "ss":
            clean_rest = rest.split("#", 1)[0]
            if "@" in clean_rest:
                user_info, host_port = clean_rest.split("@", 1)
                host, port = host_port.split(":", 1)
                return ("ss", host.lower(), int(port), user_info)
            else:
                decoded = safe_b64decode(clean_rest)
                if "@" in decoded:
                    user_info, host_port = decoded.split("@", 1)
                    host, port = host_port.split(":", 1)
                    return ("ss", host.lower(), int(port), user_info)
                return None

        parsed = urlparse(link)
        host = (parsed.hostname or "").lower()
        port = parsed.port
        if not host or not port:
            return None
        auth = parsed.username or ""
        return (scheme, host, port, auth)
    except Exception:
        return None


def apply_remark(link: str, country: str, counter: int) -> str:
    flag = "".join(chr(127397 + ord(c)) for c in country.upper()) if (country.isalpha() and len(country) == 2) else "🌐"
    new_ps = f"{flag} {country.upper()} #{counter:02d}"

    scheme = link.split("://", 1)[0].lower()
    if scheme == "vmess":
        try:
            b64_part = link.split("://", 1)[1].split("#", 1)[0]
            data = json.loads(safe_b64decode(b64_part))
            data["ps"] = new_ps
            encoded = base64.b64encode(json.dumps(data, ensure_ascii=False).encode("utf-8")).decode("utf-8")
            return f"vmess://{encoded}"
        except Exception:
            return link
    else:
        base = link.split("#", 1)[0]
        return f"{base}#{quote(new_ps)}"


def fetch_sources(file_path: str) -> list[str]:
    links = []
    if not os.path.exists(file_path):
        return links

    with open(file_path, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    headers = {
        "User-Agent": "v2rayN/6.23 Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code != 200:
                continue
            text = r.text.strip()
            
            # Пробуем декодировать base64, если это стандартная подписка
            decoded = safe_b64decode(text)
            content = decoded if "://" in decoded else text

            for raw_line in content.splitlines():
                line = raw_line.strip()
                if any(line.startswith(f"{p}://") for p in SUPPORTED_PROTOCOLS):
                    links.append(line)
        except Exception as e:
            print(f"Ошибка загрузки источника {url}: {e}")

    return links


def main():
    load_geo_cache()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    by_country_dir = os.path.join(OUTPUT_DIR, "by-country")
    os.makedirs(by_country_dir, exist_ok=True)

    raw_links = fetch_sources(SOURCES_FILE)
    print(f"Собрано сырых ссылок: {len(raw_links)}")

    seen_nodes = set()
    valid_nodes = []

    for link in raw_links:
        identity = extract_node_identity(link)
        if not identity or identity in seen_nodes:
            continue
        seen_nodes.add(identity)
        valid_nodes.append((identity, link))

    print(f"Уникальных нод после фильтрации: {len(valid_nodes)}")

    nodes_by_protocol = {proto: [] for proto in ["vless", "vmess", "trojan", "ss", "hysteria2", "tuic"]}
    nodes_by_country = {}
    reality_nodes = []
    all_final_links = []
    country_counters = {}

    for (scheme, host, _, _), link in valid_nodes:
        if scheme == "hy2":
            scheme = "hysteria2"
        country = get_country_code(host)

        country_counters[country] = country_counters.get(country, 0) + 1
        formatted_link = apply_remark(link, country, country_counters[country])

        if scheme in nodes_by_protocol:
            nodes_by_protocol[scheme].append(formatted_link)

        if "security=reality" in formatted_link.lower():
            reality_nodes.append(formatted_link)

        nodes_by_country.setdefault(country.lower(), []).append(formatted_link)
        all_final_links.append(formatted_link)

    # 1. Сохранение списков протоколов
    for proto, items in nodes_by_protocol.items():
        path = os.path.join(OUTPUT_DIR, f"{proto}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(items))

    # 2. VLESS Reality
    with open(os.path.join(OUTPUT_DIR, "reality.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(reality_nodes))

    # 3. Общие списки
    with open(os.path.join(OUTPUT_DIR, "all.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(all_final_links))

    with open(os.path.join(OUTPUT_DIR, "all-full.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(all_final_links))

    with open(os.path.join(OUTPUT_DIR, "sub.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(all_final_links[:300]))

    with open(os.path.join(OUTPUT_DIR, "sub-full.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(all_final_links))

    # 4. По странам
    for cc, items in nodes_by_country.items():
        with open(os.path.join(by_country_dir, f"{cc}.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(items))

    # 5. Base64-подписки для клиентов (v2rayN, FoXray, Streisand)
    for target in ["all", "sub", "reality", "vless", "hysteria2", "vmess"]:
        src = os.path.join(OUTPUT_DIR, f"{target}.txt")
        if os.path.exists(src):
            with open(src, "r", encoding="utf-8") as f:
                data = f.read().strip()
            b64 = base64.b64encode(data.encode("utf-8")).decode("utf-8")
            with open(os.path.join(OUTPUT_DIR, f"{target}_b64.txt"), "w", encoding="utf-8") as f:
                f.write(b64)

    # 6. Статистика
    stats = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_nodes": len(all_final_links),
        "reality_nodes": len(reality_nodes),
        "by_protocol": {k: len(v) for k, v in nodes_by_protocol.items()},
        "by_country": {k: len(v) for k, v in nodes_by_country.items()}
    }
    with open(os.path.join(OUTPUT_DIR, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    save_geo_cache()
    print("Генерация подписок успешно завершена.")


if __name__ == "__main__":
    main()
