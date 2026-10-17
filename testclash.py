#!/usr/bin/env python3
"""Тесты конвертера Clash: ссылки, поля прокси, сборка конфига."""

from __future__ import annotations

import base64
import json
import sys

import clashout

FAILED = 0


def check(name: str, ok: bool, extra: str = "") -> None:
    global FAILED
    if ok:
        print(f"  ок      {name}")
    else:
        FAILED += 1
        print(f"  ПРОВАЛ  {name}" + (f": {extra}" if extra else ""))


class FakeNode:
    def __init__(self, raw: str, country: str = "", proto: str = "",
                 latency_ms: int | None = None) -> None:
        self.raw = raw
        self.country = country
        self.proto = proto
        self.latency_ms = latency_ms


UUID = "11111111-2222-3333-4444-555555555555"
PBK = base64.urlsafe_b64encode(b"\x07" * 32).decode().rstrip("=")

VLESS_REALITY = (
    f"vless://{UUID}@203.0.113.5:443?security=reality&sni=www.example.com"
    f"&fp=chrome&pbk={PBK}&sid=9f1a&type=tcp&flow=xtls-rprx-vision#r"
)
VLESS_WS = (
    f"vless://{UUID}@203.0.113.6:8080?security=tls&type=ws"
    f"&host=cdn.example.com&path=%2Fws&sni=cdn.example.com&fp=firefox#w"
)
VMESS = "vmess://" + base64.b64encode(json.dumps({
    "v": "2", "ps": "v", "add": "203.0.113.12", "port": "443",
    "id": UUID, "aid": "0", "scy": "chacha20-poly1305", "net": "ws",
    "type": "none", "host": "vm.example.com", "path": "/vm", "tls": "tls",
    "sni": "vm.example.com",
}).encode("utf-8")).decode("ascii")
TROJAN = "trojan://secret@203.0.113.7:443?sni=example.com&type=tcp#t"
SS_A = ("ss://" + base64.urlsafe_b64encode(b"aes-256-gcm:pass123")
        .decode().rstrip("=") + "@203.0.113.8:8388#ss")
SS_B = ("ss://" + base64.urlsafe_b64encode(b"chacha20-ietf-poly1305:pw"
        + b"@203.0.113.9:8389").decode().rstrip("=") + "#ss2")
HY2 = ("hysteria2://pw2@203.0.113.10:443?sni=hy.example.com"
       "&obfs=salamander&obfs-password=salt#hy")
TUIC = (f"tuic://{UUID}:pw3@203.0.113.11:443?sni=tuic.example.com"
        f"&congestion_control=bbr&udp_relay_mode=native#tu")

ALL_LINKS = [VLESS_REALITY, VLESS_WS, VMESS, TROJAN, SS_A, SS_B, HY2, TUIC]

BAD_LINKS = [
    "",
    "   ",
    "мусор",
    "vless://",
    f"vless://{UUID}@203.0.113.5",
    "vless://@203.0.113.5:443",
    "trojan://@203.0.113.7:443",
    "trojan://secret",
    "ss://не-настоящий-метод",
    "ss://" + base64.b64encode(b"rc4-md5:pw@1.2.3.4:8388").decode().rstrip("="),
    "hysteria2://203.0.113.10:443",
    "hysteria2://@",
    "tuic://203.0.113.11:443",
    "tuic://not-a-uuid:pw@203.0.113.11:443",
    f"tuic://{UUID}@203.0.113.11:443",
    "vmess://@@@@",
    "vmess://" + base64.b64encode("не json".encode("utf-8")).decode(),
    "ссылка://неизвестный-протокол",
]


print("1. Разбор ссылок по протоколам")
proxies = {}
for link in ALL_LINKS:
    proxy = clashout.clash_proxy(FakeNode(link, country="NL", proto="x", latency_ms=50))
    proxies[link] = proxy
    check(f"разобралась {link.split('://')[0]}",
          isinstance(proxy, dict), "конвертер вернул None")

vless = proxies[VLESS_REALITY] or {}
check("vless reality: tls включён", vless.get("tls") is True)
check("vless reality: servername", vless.get("servername") == "www.example.com")
check("vless reality: flow",
      vless.get("flow") == "xtls-rprx-vision")
check("vless reality: отпечаток",
      vless.get("client-fingerprint") == "chrome")
check("vless reality: ключ reality",
      (vless.get("reality-opts") or {}).get("public-key") == PBK)
check("vless reality: short-id",
      (vless.get("reality-opts") or {}).get("short-id") == "9f1a")

vless_ws = proxies[VLESS_WS] or {}
check("vless ws: сеть", vless_ws.get("network") == "ws")
check("vless ws: путь",
      (vless_ws.get("ws-opts") or {}).get("path") == "/ws")
check("vless ws: заголовок Host",
      ((vless_ws.get("ws-opts") or {}).get("headers") or {}).get("Host")
      == "cdn.example.com")
check("vless ws: отпечаток",
      vless_ws.get("client-fingerprint") == "firefox")

vmess = proxies[VMESS] or {}
check("vmess: тип и uuid",
      vmess.get("type") == "vmess" and vmess.get("uuid") == UUID)
check("vmess: шифр из scy",
      vmess.get("cipher") == "chacha20-poly1305")
check("vmess: сеть ws", vmess.get("network") == "ws")
check("vmess: tls и sni",
      vmess.get("tls") is True and vmess.get("servername") == "vm.example.com")

trojan = proxies[TROJAN] or {}
check("trojan: тип и пароль",
      trojan.get("type") == "trojan" and trojan.get("password") == "secret")
check("trojan: sni", trojan.get("sni") == "example.com")
check("trojan: tls включён", trojan.get("tls") is True)

check("ss: метод и пароль (вариант с @)",
      (proxies[SS_A] or {}).get("cipher") == "aes-256-gcm"
      and (proxies[SS_A] or {}).get("password") == "pass123")
check("ss: разбор целиком в base64",
      (proxies[SS_B] or {}).get("cipher") == "chacha20-ietf-poly1305"
      and (proxies[SS_B] or {}).get("port") == 8389)

hy2 = proxies[HY2] or {}
check("hysteria2: тип и пароль",
      hy2.get("type") == "hysteria2" and hy2.get("password") == "pw2")
check("hysteria2: obfs",
      hy2.get("obfs") == "salamander"
      and hy2.get("obfs-password") == "salt")
check("hysteria2: sni", hy2.get("sni") == "hy.example.com")

tuic = proxies[TUIC] or {}
check("tuic: тип, uuid и пароль",
      tuic.get("type") == "tuic" and tuic.get("uuid") == UUID
      and tuic.get("password") == "pw3")
check("tuic: контроль перегрузки",
      tuic.get("congestion-controller") == "bbr")
check("tuic: режим udp",
      tuic.get("udp-relay-mode") == "native")


print("2. Битые ссылки не ломают конвертер")
for link in BAD_LINKS:
    try:
        result = clashout.clash_proxy(FakeNode(link))
    except Exception as exc:            # noqa: BLE001
        check(f"битая ссылка {link[:24]!r} не бросила исключение", False,
              f"{type(exc).__name__}: {exc}")
        continue
    check(f"битая ссылка {link[:24]!r} пропущена", result is None,
          f"вернулся {result}")
check("объект без raw пропущен",
      clashout.clash_proxy(object()) is None)


print("3. Сборка конфига")
nodes = [
    FakeNode(link, country=country, proto=link.split("://")[0], latency_ms=40 + i)
    for i, (link, country) in enumerate(zip(ALL_LINKS, [
        "NL", "DE", "DE", "US", "NL", "NL", "NL", "NL",
    ]))
]
text = clashout.build_clash(nodes)
check("результат это строка", isinstance(text, str))
check("есть секция proxies", "proxies:" in text)
check("есть секция proxy-groups", "proxy-groups:" in text)
check("есть секция rules", "rules:" in text)
check("есть правило MATCH,Авто", "MATCH,Авто" in text)
check("есть группа Авто с url-test",
      'type: "url-test"' in text and '"Авто"' in text)
check("есть группа Ручной", '"Ручной"' in text)
check("группа страны NL появилась (5 узлов)", "NL" in text)

parsed = None
try:
    import yaml
except ImportError:
    print("  ~       PyYAML не установлен: разбор YAML пропущен")
else:
    try:
        parsed = yaml.safe_load(text)
    except Exception as exc:            # noqa: BLE001
        check("YAML разбирается", False, f"{type(exc).__name__}: {exc}")

if parsed is not None:
    check("YAML разбирается", isinstance(parsed, dict))
    got = parsed.get("proxies") or []
    check("все узлы попали в конфиг", len(got) == len(ALL_LINKS),
          f"{len(got)} из {len(ALL_LINKS)}")
    check("у каждого прокси есть обязательные поля",
          all(p.get("name") and p.get("type") and p.get("server") and p.get("port")
              for p in got))
    names = [p.get("name") for p in got]
    check("имена прокси уникальны", len(names) == len(set(names)))
    groups = parsed.get("proxy-groups") or []
    check("группы ссылаются на существующие прокси",
          all(set(g.get("proxies") or []) <= set(names) for g in groups))
    check("режим rule и mixed-port",
          parsed.get("mode") == "rule" and parsed.get("mixed-port") == 7890)

print("4. Имена и пустой список")
text = clashout.build_clash(nodes[:2], labels=["Мой узел", "Мой узел"])
check("одинаковые имена разведены",
      text.count('name: "Мой узел') == 2 and "Мой узел #2" in text)

empty = clashout.build_clash([])
check("пустой список даёт валидный конфиг",
      "proxies: []" in empty and "MATCH,DIRECT" in empty)
if parsed is not None:
    try:
        check("пустой конфиг разбирается",
              isinstance(yaml.safe_load(empty), dict))
    except Exception as exc:            # noqa: BLE001
        check("пустой конфиг разбирается", False, str(exc))

print("5. Сборка на настоящей подписке")
try:
    lines = open("output/all-full.txt", encoding="utf-8").read().splitlines()
except OSError:
    print("  ~       output/all-full.txt не найден: проверка пропущена")
else:
    real = [FakeNode(line, country="US", proto="x") for line in lines[:300] if line]
    real_text = clashout.build_clash(real)
    converted = real_text.count('server: "')
    check(f"из {len(real)} строк собрался конфиг ({converted} прокси)",
          converted > 0)
    if parsed is not None:
        data = yaml.safe_load(real_text)
        check("настоящий конфиг разбирается",
              isinstance(data, dict) and len(data.get("proxies") or []) == converted)

if FAILED:
    print(f"\nПРОВАЛОВ: {FAILED}")
    sys.exit(1)
print("\nВсе проверки пройдены.")
