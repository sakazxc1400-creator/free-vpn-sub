#!/usr/bin/env python3
"""
Проверка, что сгенерированные конфиги sing-box действительно валидны.
Запускает `sing-box check` на конфиге, собранном из синтетических ссылок.

Требует бинарник sing-box. Без него тест сообщает об этом и выходит с 0,
чтобы не блокировать прогон там, где бинарника нет.

Запуск:  py testsingbox.py
"""

import json
import subprocess
import sys
import tempfile
from base64 import b64encode
from pathlib import Path

import outbound
import probe

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [ok] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")
        failures.append(name)


def b64(s: str) -> str:
    return b64encode(s.encode()).decode()


binary = probe.find_singbox()
if not binary:
    print("sing-box не найден — проверка конфигов пропущена.")
    sys.exit(0)

print(f"== {binary} ==")

# По одной ссылке на каждый поддерживаемый вариант.
LINKS = [
    ("vless+ws+tls",
     "vless://11111111-2222-3333-4444-555555555555@1.2.3.4:443"
     "?type=ws&security=tls&sni=a.com&path=%2Fws&host=b.com&fp=chrome#n"),
    ("vless+reality",
     "vless://11111111-2222-3333-4444-555555555555@5.6.7.8:443"
     "?security=reality&pbk=jNXHt1yRo0vDuchQlIP6Z0ZvjT3KtzVI-T4E7RoLJS0"
     "&sid=6ba85179e30d4fc2&sni=ya.ru&flow=xtls-rprx-vision&type=tcp#r"),
    ("vless+grpc",
     "vless://11111111-2222-3333-4444-555555555555@9.9.9.9:443"
     "?type=grpc&serviceName=svc&security=tls&sni=g.com#g"),
    ("vless+httpupgrade",
     "vless://11111111-2222-3333-4444-555555555555@9.9.9.8:443"
     "?type=httpupgrade&security=tls&host=u.com&path=%2Fu#hu"),
    ("vmess+ws+tls",
     "vmess://" + b64(json.dumps({
         "add": "3.3.3.3", "port": "8443",
         "id": "22222222-3333-4444-5555-666666666666",
         "aid": "0", "net": "ws", "path": "/p", "host": "h.com",
         "tls": "tls", "scy": "auto",
     }))),
    ("vmess+tcp",
     "vmess://" + b64(json.dumps({
         "add": "4.4.4.4", "port": 80,
         "id": "33333333-4444-5555-6666-777777777777",
         "net": "tcp", "scy": "none",
     }))),
    ("trojan+tls",
     "trojan://pw123@7.7.7.7:443?sni=t.com&allowInsecure=1#t"),
    ("trojan+ws",
     "trojan://pw123@7.7.7.6:443?type=ws&path=%2Fw&host=tw.com&sni=tw.com#tw"),
    ("shadowsocks",
     "ss://" + b64("aes-256-gcm:secret") + "@8.8.8.8:8388#s"),
    ("shadowsocks-2022",
     "ss://" + b64("2022-blake3-aes-128-gcm:AAAAAAAAAAAAAAAAAAAAAA==")
     + "@8.8.8.7:8389#s22"),
    ("hysteria2",
     "hy2://pass@6.6.6.6:8443?insecure=1&sni=h.com"
     "&obfs=salamander&obfs-password=op#h"),
    ("hysteria2-plain",
     "hysteria2://pass2@6.6.6.5:443?sni=h2.com#h2"),
    ("tuic",
     "tuic://44444444-5555-6666-7777-888888888888:pw@2.2.2.2:443"
     "?congestion_control=bbr&alpn=h3&sni=tu.com#tu"),
]

print("== конвертация ==")
built: list[tuple[str, dict]] = []
for name, link in LINKS:
    out = outbound.build(link)
    check(f"{name} собран", out is not None)
    if out is not None:
        built.append((name, out))

print("== каждый outbound по отдельности ==")
for name, out in built:
    config = {
        "log": {"level": "fatal"},
        "inbounds": [{
            "type": "http", "tag": "in",
            "listen": "127.0.0.1", "listen_port": 27999,
        }],
        "outbounds": [dict(out, tag="proxy")],
        "route": {"rules": [{"inbound": ["in"], "outbound": "proxy"}]},
    }
    tmp = tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    )
    try:
        json.dump(config, tmp)
        tmp.close()
        result = subprocess.run(
            [binary, "check", "-c", tmp.name],
            capture_output=True, text=True, timeout=30,
        )
        detail = (result.stderr or result.stdout).strip().splitlines()
        check(f"{name} валиден для sing-box", result.returncode == 0,
              detail[-1] if detail else "")
    finally:
        Path(tmp.name).unlink(missing_ok=True)

print("== общий конфиг со всеми узлами ==")
pairs = [(24000 + i, out) for i, (_, out) in enumerate(built)]
config = probe.build_config(pairs)
tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
try:
    json.dump(config, tmp)
    tmp.close()
    result = subprocess.run(
        [binary, "check", "-c", tmp.name], capture_output=True, text=True, timeout=60
    )
    detail = (result.stderr or result.stdout).strip().splitlines()
    check("конфиг probe.build_config валиден", result.returncode == 0,
          detail[-1] if detail else "")
    check("инбаундов = узлов", len(config["inbounds"]) == len(pairs))
    check("аутбаундов = узлов", len(config["outbounds"]) == len(pairs))
    check("правил маршрутизации = узлов + reject",
          len(config["route"]["rules"]) == len(pairs) + 1)
    check("последнее правило — reject",
          config["route"]["rules"][-1] == {"action": "reject"})
    tags = [o["tag"] for o in config["outbounds"]]
    check("теги уникальны", len(tags) == len(set(tags)))
    check("DNS в новом формате",
          config["dns"]["servers"][0].get("type") == "udp",
          str(config["dns"]["servers"][0]))
finally:
    Path(tmp.name).unlink(missing_ok=True)

print("== реальный запуск: узлы недоступны, но sing-box стартует ==")
# Узлы фиктивные, поэтому рабочих быть не должно. Проверяем, что процесс
# поднимается и корректно возвращает пустой результат, а не падает.


class FakeNode:
    def __init__(self, link):
        self.raw = link


nodes = [FakeNode(link) for _, link in LINKS[:4]]
results = probe.verify_batch(nodes, binary)
check("процесс не упал", isinstance(results, list))
check("фиктивные узлы не прошли проверку", results == [], str(results))

print()
if failures:
    print(f"ПРОВАЛЕНО: {len(failures)} -> {failures}")
    sys.exit(1)
print("Все конфиги валидны для sing-box.")
