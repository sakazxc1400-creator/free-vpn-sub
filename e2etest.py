#!/usr/bin/env python3
"""End-to-end прогон collect.main() на локальном сервере, без внешней сети."""

import base64
import http.server
import json
import os
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


# живые TCP-порты, чтобы проверка доступности их нашла
live_servers = []
live_ports = []
for _ in range(3):
    srv = socketserver.TCPServer(("127.0.0.1", 0), socketserver.BaseRequestHandler)
    live_ports.append(srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    live_servers.append(srv)

DEAD_PORT = 1  # почти наверняка закрыт

# loopback разрешаем ниже, иначе is_routable его отбросит
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
    # тест должен начинаться с пустой истории
    history_file = ROOT / "output" / "history.json"
    if history_file.exists():
        history_file.unlink()

    (ROOT / "sources.txt").write_text("\n".join([
        "# e2e",
        f"{base_url}/plain",
        f"{base_url}/b64",
        f"{base_url}/empty",
        f"{base_url}/junk",
        f"{base_url}/fail",
    ]) + "\n", encoding="utf-8")

    collect.is_routable = lambda host: True
    collect.CHECK_TIMEOUT = 1.0
    # иначе сработала бы защита от плохой сборки
    os.environ["ALLOW_SHRINK"] = "1"
    collect.STABLE_RUNS = 2
    # sing-box не запускаем: проверяем откат на TCP
    collect.probe.verify = lambda nodes, need: []
    collect.probe.measure_speed = lambda nodes, singbox=None: 0
    # вместо сети отдаём фиксированную страну
    collect.geo.annotate = lambda hosts: {h: "NL" for h in hosts}

    print("== прогон collect.main() ==")
    rc = collect.main()
    check("main() вернул 0", rc == 0, f"rc={rc}")

    out = ROOT / "output"
    for fname in ("sub.txt", "all.txt", "sub-full.txt", "all-full.txt",
                  "sub-stable.txt", "all-stable.txt", "nodes.json",
                  "history.json", "clash.yaml", "stats.json"):
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

    print("== nodes.json, история, Clash ==")
    nodes_json = json.loads((out / "nodes.json").read_text(encoding="utf-8"))
    check("nodes.json совпадает с основной подпиской",
          len(nodes_json) == stats["published"],
          f"{len(nodes_json)} != {stats['published']}")
    check("в nodes.json есть адрес, страна и задержка",
          all(n.get("addr") and n.get("name") and n.get("ms") is not None
              and n.get("cc") for n in nodes_json), str(nodes_json[:2]))
    check("в nodes.json есть срок жизни", all("up" in n for n in nodes_json))
    check("в nodes.json есть ссылки для своей подписки",
          all(str(n.get("url", "")).startswith(("vless://", "vmess://", "trojan://",
                                               "ss://", "hysteria2://", "tuic://"))
              for n in nodes_json), str(nodes_json[:1])[:200])

    history = json.loads((out / "history.json").read_text(encoding="utf-8"))
    check("история знает все узлы", history.get("count") == 3,
          str(history.get("count")))
    check("первый прогон: стаж 1",
          all(v.get("streak") == 1 for v in history["nodes"].values()),
          str(history["nodes"]))
    check("стабильная подписка пока пуста",
          (out / "all-stable.txt").read_text(encoding="utf-8").strip() == "")
    check("в stats есть stable и tls_ok",
          stats["stable"] == 0 and stats["tls_ok"] == 3, str(stats))

    clash = (out / "clash.yaml").read_text(encoding="utf-8")
    check("clash.yaml содержит прокси и правило",
          "proxies:" in clash and "MATCH," in clash)
    check("в clash.yaml есть группа Авто", '"Авто"' in clash)
    try:
        import yaml
    except ImportError:
        print("     PyYAML нет: разбор clash.yaml пропущен")
    else:
        parsed_clash = yaml.safe_load(clash)
        check("clash.yaml разбирается как YAML",
              isinstance(parsed_clash, dict)
              and len(parsed_clash.get("proxies") or []) == stats["published"],
              str(type(parsed_clash)))

    print("== сценарий: все источники недоступны ==")
    before = (out / "sub.txt").read_text(encoding="utf-8")
    (ROOT / "sources.txt").write_text(f"{base_url}/fail\n", encoding="utf-8")
    rc2 = collect.main()
    after = (out / "sub.txt").read_text(encoding="utf-8")
    check("main() вернул ошибку", rc2 == 1, f"rc={rc2}")
    check("старая подписка не затёрта", before == after)

    print("== сценарий: источник без узлов ==")
    (ROOT / "sources.txt").write_text(f"{base_url}/junk\n", encoding="utf-8")
    rc3 = collect.main()
    after2 = (out / "sub.txt").read_text(encoding="utf-8")
    check("main() вернул ошибку", rc3 == 1, f"rc={rc3}")
    check("старая подписка не затёрта", before == after2)

    print("== сценарий: проверка через sing-box ==")
    (ROOT / "sources.txt").write_text("\n".join([
        f"{base_url}/plain", f"{base_url}/b64",
    ]) + "\n", encoding="utf-8")

    def fake_verify(nodes, need):
        # у второго сертификат не проверился, он должен идти ниже
        result = []
        for i, node in enumerate(nodes[:2]):
            node.tls_ok = i == 0
            node.speed_mbps = 5.0 if i == 0 else None
            result.append((node, 40 + i * 10))
        return result

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

    lines4 = [l for l in urllib.parse.unquote(plain4).splitlines() if l.strip()]
    check("узел с проверенным сертификатом стоит первым", "⚠" not in lines4[0])
    check("узел с непроверенным сертификатом помечен", "⚠" in lines4[1],
          lines4[1][:120])
    check("посчитаны узлы с проверенным сертификатом", stats4["tls_ok"] == 1,
          str(stats4["tls_ok"]))

    # второй прогон: те же адреса, значит стабильные
    rc5 = collect.main()
    stats5 = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    check("второй прогон прошёл", rc5 == 0, f"rc={rc5}")
    check("стабильная подписка наполнилась", stats5["stable"] >= 1,
          str(stats5["stable"]))
    stable_plain = (out / "all-stable.txt").read_text(encoding="utf-8")
    check("в стабильной подписке есть узлы", stable_plain.strip() != "")
    check("в названии узла виден срок жизни",
          "ч" in urllib.parse.unquote(stable_plain),
          urllib.parse.unquote(stable_plain)[:200])

    print("== сценарий: защита от плохой сборки ==")
    os.environ.pop("ALLOW_SHRINK", None)
    spoiled = dict(stats5)
    spoiled["published_full"] = 1000
    (out / "stats.json").write_text(json.dumps(spoiled), encoding="utf-8")
    before_guard = (out / "all.txt").read_text(encoding="utf-8")
    rc6 = collect.main()
    check("прогон остановлен", rc6 == 1, f"rc={rc6}")
    check("подписка не перезаписана",
          (out / "all.txt").read_text(encoding="utf-8") == before_guard)
    os.environ["ALLOW_SHRINK"] = "1"

finally:
    httpd.shutdown()
    for s in live_servers:
        s.shutdown()
    if (BACKUP / "sources.txt").exists():
        shutil.copy2(BACKUP / "sources.txt", ROOT / "sources.txt")
    if (ROOT / "output").exists():
        shutil.rmtree(ROOT / "output")
    if (BACKUP / "output").exists():
        shutil.copytree(BACKUP / "output", ROOT / "output")
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
