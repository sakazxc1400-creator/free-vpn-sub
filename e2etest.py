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

    print("== прогон collect.main() ==")
    rc = collect.main()
    check("main() вернул 0", rc == 0, f"rc={rc}")

    out = ROOT / "output"
    for fname in ("sub.txt", "all.txt", "stats.json"):
        check(f"{fname} создан", (out / fname).exists())

    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    print(f"     stats: {json.dumps(stats, ensure_ascii=False)}")

    check("sources_total = 5", stats["sources_total"] == 5, str(stats["sources_total"]))
    check("часть источников упала", len(stats["sources_failed"]) >= 1)
    check("узлы распарсены", stats["parsed"] >= 4, str(stats["parsed"]))
    check("дубликат отброшен", stats["unique"] < stats["parsed"], f"{stats['unique']}/{stats['parsed']}")
    check("живых ровно 3", stats["alive"] == 3, str(stats["alive"]))
    check("мёртвые отброшены", stats["alive"] < stats["unique"])
    check("best_latency не None", stats["best_latency_ms"] is not None)

    plain = (out / "all.txt").read_text(encoding="utf-8")
    check("в all.txt 3 строки", len([l for l in plain.splitlines() if l.strip()]) == 3)
    check("нет мёртвого порта", f":{DEAD_PORT}#" not in plain and f":{DEAD_PORT}?" not in plain)

    decoded = base64.b64decode((out / "sub.txt").read_text(encoding="utf-8")).decode()
    check("sub.txt = валидный base64 от all.txt", decoded.strip() == plain.strip())
    check("в подписке есть latency-метки", "ms" in decoded)

    check("файл по протоколу создан", (out / "vless.txt").exists())
    check("by_protocol заполнен", len(stats["by_protocol"]) >= 2, str(stats["by_protocol"]))

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
    shutil.rmtree(BACKUP)
    print("== файлы восстановлены ==")

print()
if failures:
    print(f"ПРОВАЛЕНО: {len(failures)} -> {failures}")
    sys.exit(1)
print("E2E пройден.")
