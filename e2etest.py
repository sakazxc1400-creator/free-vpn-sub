#!/usr/bin/env python3
"""
End-to-end проверка пайплайна без внешней сети.

Поднимает локальный HTTP-сервер, который отдаёт поддельные подписки,
подменяет sources.txt и слушающие порты, затем гоняет collect.main().
Проверяет, что output/* создаются корректно.

Запуск:  py e2etest.py
"""

import base64
import http.server
import json
import shutil
import socket
import socketserver
import sys
import threading
import urllib.parse
from pathlib import Path

import collect

ROOT = Path(__file__).resolve().parent
BACKUP = ROOT / "_e2e_backup"

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [ok] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")
        failures.append(name)


def b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


# --- Поднимаем "живые" TCP-порты, чтобы проверка доступности их нашла ---
live_servers = []
live_ports = []
for _ in range(3):
    srv = socketserver.TCPServer(("127.0.0.1", 0), socketserver.BaseRequestHandler)
    live_ports.append(srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    live_servers.append(srv)

DEAD_PORT = 1  # порт 1 почти наверняка закрыт

# --- Готовим поддельные подписки ---
# Живые узлы (127.0.0.1 нормально не пройдёт is_routable, поэтому
# для e2e временно разрешаем loopback).
plain_sub = "\n".join([
    f"vless://uuid-aaa-111@127.0.0.1:{live_ports[0]}?type=tcp&sni=a.com#live-1",
    f"trojan://pass123@127.0.0.1:{live_ports[1]}?sni=b.com#live-2",
    f"vless://uuid-aaa-111@127.0.0.1:{live_ports[0]}?type=tcp&sni=a.com#dup-of-live-1",
    f"vless://uuid-ccc-333@127.0.0.1:{DEAD_PORT}?type=tcp#dead-1",
    "vless://broken-no-port@127.0.0.1#invalid",
    "not-a-link-at-all",
])

b64_sub = b64("\n".join([
    "vmess://" + b64(json.dumps({
        "add": "127.0.0.1", "port": str(live_ports[2]),
        "id": "vmess-id-999", "net": "ws",
    })),
    f"ss://{b64('aes-256-gcm:pw')}@127.0.0.1:{DEAD_PORT}#dead-ss",
]))

PAGES = {"/plain": plain_sub, "/b64": b64_sub, "/empty": "", "/junk": "<html>404</html>"}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/fail":
            self.send_error(500)
            return
        body = PAGES.get(self.path)
        if body is None:
            self.send_error(404)
            return
        raw = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)
port = httpd.server_address[1]
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base_url = f"http://127.0.0.1:{port}"

print(f"== локальный сервер на {base_url} ==")

# --- Бэкап реальных файлов ---
if BACKUP.exists():
    shutil.rmtree(BACKUP)
BACKUP.mkdir()
for name in ("sources.txt",):
    if (ROOT / name).exists():
        shutil.copy2(ROOT / name, BACKUP / name)
if (ROOT / "output").exists():
    shutil.copytree(ROOT / "output", BACKUP / "output")

exit_code = 1
GEO_BACKUP = BACKUP / "geo_cache.json"
if (ROOT / "geo_cache.json").exists():
    shutil.copy2(ROOT / "geo_cache.json", GEO_BACKUP)

try:
    # Подменяем источники.
    (ROOT / "sources.txt").write_text("\n".join([
        "# e2e",
        f"{base_url}/plain",
        f"{base_url}/b64",
        f"{base_url}/empty",
        f"{base_url}/junk",
        f"{base_url}/fail",
    ]) + "\n", encoding="utf-8")

    # Разрешаем loopback только на время теста.
    collect.is_routable = lambda host: True
    collect.CHECK_TIMEOUT = 1.0
    # sing-box в тесте не запускаем: проверяем именно откат на TCP-режим.
    collect.probe.verify = lambda nodes, need: []
    # Сеть для гео не трогаем, подставляем фиксированные страны.
    collect.geo.annotate = lambda hosts: {h: "NL" for h in hosts}

    print("== прогон collect.main() ==")
    rc = collect.main()
    check("main() вернул 0", rc == 0, f"rc={rc}")

    out = ROOT / "output"
    for fname in ("sub.txt", "all.txt", "sub-full.txt", "all-full.txt",
                  "stats.json"):
        check(f"{fname} создан", (out / fname).exists())

    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    print(f"     stats: {json.dumps(stats, ensure_ascii=False)}")

    check("sources_total = 5", stats["sources_total"] == 5, str(stats["sources_total"]))
    check("часть источников упала", len(stats["sources_failed"]) >= 1)
    check("узлы распарсены", stats["parsed"] >= 4, str(stats["parsed"]))
    check("дубликат отброшен", stats["unique"] < stats["parsed"], f"{stats['unique']}/{stats['parsed']}")
    check("tcp_alive = 3", stats["tcp_alive"] == 3, str(stats["tcp_alive"]))
    check("мёртвые отброшены", stats["tcp_alive"] < stats["unique"])
    check("verified = 0 без sing-box", stats["verified"] == 0, str(stats["verified"]))
    check("best_latency не None", stats["best_latency_ms"] is not None)
    check("median_latency не None", stats["median_latency_ms"] is not None)
    check("countries посчитаны", stats["countries"] == 1, str(stats["countries"]))

    plain = (out / "all.txt").read_text(encoding="utf-8")
    check("в all.txt 3 строки", len([l for l in plain.splitlines() if l.strip()]) == 3)
    check("нет мёртвого порта", f":{DEAD_PORT}#" not in plain and f":{DEAD_PORT}?" not in plain)

    decoded = base64.b64decode((out / "sub.txt").read_text(encoding="utf-8")).decode()
    check("sub.txt = валидный base64 от all.txt", decoded.strip() == plain.strip())
    check("в подписке есть latency-метки", "ms" in decoded)
    check("в подписке есть флаг страны",
          "%F0%9F%87%B3%F0%9F%87%B1" in decoded or "\U0001F1F3\U0001F1F1" in decoded,
          decoded[:200])

    check("файл по протоколу создан", (out / "vless.txt").exists())
    check("by_protocol заполнен", len(stats["by_protocol"]) >= 2, str(stats["by_protocol"]))
    check("папка by-country создана", (out / "by-country").is_dir())
    check("файл страны создан", (out / "by-country" / "nl.txt").exists())
    check("by_country заполнен", stats["by_country"].get("NL") == 3,
          str(stats["by_country"]))

    # --- Лимиты размера подписок ---
    print("== лимиты размера подписок ==")
    check("не больше MAX_OUTPUT",
          stats["published"] <= collect.MAX_OUTPUT,
          f"{stats['published']}>{collect.MAX_OUTPUT}")
    check("MAX_OUTPUT разумный для клиентов",
          collect.MAX_OUTPUT <= 300, str(collect.MAX_OUTPUT))
    check("не больше MAX_FULL",
          stats["published_full"] <= collect.MAX_FULL,
          f"{stats['published_full']}>{collect.MAX_FULL}")
    check("полная не меньше основной",
          stats["published_full"] >= stats["published"],
          f"{stats['published_full']}<{stats['published']}")
    check("MAX_FULL больше MAX_OUTPUT",
          collect.MAX_FULL > collect.MAX_OUTPUT,
          f"{collect.MAX_FULL}<={collect.MAX_OUTPUT}")

    full_plain = (out / "all-full.txt").read_text(encoding="utf-8")
    full_decoded = base64.b64decode(
        (out / "sub-full.txt").read_text(encoding="utf-8")
    ).decode()
    check("sub-full.txt = валидный base64 от all-full.txt",
          full_decoded.strip() == full_plain.strip())
    check("в all-full.txt 3 строки",
          len([l for l in full_plain.splitlines() if l.strip()]) == 3)

    # --- Сценарий: все источники мертвы -> подписка не должна затираться ---
    print("== сценарий: все источники недоступны ==")
    before = (out / "sub.txt").read_text(encoding="utf-8")
    (ROOT / "sources.txt").write_text(f"{base_url}/fail\n", encoding="utf-8")
    rc2 = collect.main()
    after = (out / "sub.txt").read_text(encoding="utf-8")
    check("main() вернул ошибку", rc2 == 1, f"rc={rc2}")
    check("старая подписка не затёрта", before == after)

    # --- Сценарий: источник отвечает, но узлов нет ---
    print("== сценарий: источник без узлов ==")
    (ROOT / "sources.txt").write_text(f"{base_url}/junk\n", encoding="utf-8")
    rc3 = collect.main()
    after2 = (out / "sub.txt").read_text(encoding="utf-8")
    check("main() вернул ошибку", rc3 == 1, f"rc={rc3}")
    check("старая подписка не затёрта", before == after2)

    # --- Сценарий: sing-box работает и часть узлов реально живая ---
    print("== сценарий: проверка через sing-box ==")
    (ROOT / "sources.txt").write_text("\n".join([
        f"{base_url}/plain", f"{base_url}/b64",
    ]) + "\n", encoding="utf-8")

    def fake_verify(nodes, need):
        # Первые два узла "работают", остальные нет.
        return [(n, 40 + i * 10) for i, n in enumerate(nodes[:2])]

    collect.probe.verify = fake_verify
    rc4 = collect.main()
    stats4 = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    check("main() вернул 0", rc4 == 0, f"rc={rc4}")
    check("verified заполнен", stats4["verified"] == 2, str(stats4["verified"]))
    check("published = verified", stats4["published"] == 2, str(stats4["published"]))
    plain4 = (out / "all.txt").read_text(encoding="utf-8")
    check("в подписке только проверенные",
          len([l for l in plain4.splitlines() if l.strip()]) == 2)
    check("задержка из проверки", "40ms" in urllib.parse.unquote(plain4), plain4[:200])

finally:
    httpd.shutdown()
    for s in live_servers:
        s.shutdown()
    # Восстанавливаем.
    if (BACKUP / "sources.txt").exists():
        shutil.copy2(BACKUP / "sources.txt", ROOT / "sources.txt")
    if (ROOT / "output").exists():
        shutil.rmtree(ROOT / "output")
    if (BACKUP / "output").exists():
        shutil.copytree(BACKUP / "output", ROOT / "output")
    # Кэш гео, созданный тестом, не должен попасть в репозиторий.
    if GEO_BACKUP.exists():
        shutil.copy2(GEO_BACKUP, ROOT / "geo_cache.json")
    elif (ROOT / "geo_cache.json").exists():
        (ROOT / "geo_cache.json").unlink()
    shutil.rmtree(BACKUP)
    print("== файлы восстановлены ==")

print()
if failures:
    print(f"ПРОВАЛЕНО: {len(failures)} -> {failures}")
    sys.exit(1)
print("E2E пройден.")
