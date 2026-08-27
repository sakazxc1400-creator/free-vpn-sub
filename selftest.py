#!/usr/bin/env python3
"""
Офлайн-тесты парсеров. Сеть не нужна.
Запуск:  py selftest.py
"""

import base64
import json
import sys

from collect import (
    Node,
    b64_decode_loose,
    extract_links,
    is_routable,
    parse_link,
    retag,
    split_host_port,
)

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [ok] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")
        failures.append(name)


def b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


print("== split_host_port ==")
check("ipv4", split_host_port("1.2.3.4:443") == ("1.2.3.4", 443))
check("domain", split_host_port("cdn.example.com:8443") == ("cdn.example.com", 8443))
check("ipv6", split_host_port("[2606:4700::1111]:443") == ("2606:4700::1111", 443))
check("no port -> None", split_host_port("1.2.3.4") == (None, None))
check("bad port -> None", split_host_port("1.2.3.4:abc") == (None, None))
check("port 0 -> None", split_host_port("1.2.3.4:0") == (None, None))
check("port 99999 -> None", split_host_port("1.2.3.4:99999") == (None, None))
check("private ip -> None", split_host_port("192.168.1.1:443") == (None, None))
check("loopback -> None", split_host_port("127.0.0.1:443") == (None, None))
check("empty -> None", split_host_port("") == (None, None))

print("== is_routable ==")
check("public ip", is_routable("8.8.8.8"))
check("domain", is_routable("a.example.com"))
check("localhost", not is_routable("localhost"))
check("private", not is_routable("10.0.0.1"))
check("0.0.0.0", not is_routable("0.0.0.0"))
check("bare word", not is_routable("server"))

print("== base64 ==")
check("plain roundtrip", b64_decode_loose(b64("hello world hello world")) == "hello world hello world")
check("no padding", b64_decode_loose(b64("hello world hello world").rstrip("=")) is not None)
check("not b64", b64_decode_loose("vless://abc@1.2.3.4:443") is None)
check("too short", b64_decode_loose("aGk=") is None)

print("== parse vless ==")
n = parse_link("vless://d1e2f3a4-1111-2222-3333-444455556666@1.2.3.4:443?type=tcp&security=reality&sni=ya.ru#Node")
check("parsed", n is not None)
check("proto", n and n.proto == "vless")
check("host", n and n.host == "1.2.3.4")
check("port", n and n.port == 443)
check("sni in ident", n and "ya.ru" in n.ident)
check("no uuid -> None", parse_link("vless://@1.2.3.4:443") is None)
check("no port -> None", parse_link("vless://uuid@1.2.3.4") is None)

print("== parse vmess ==")
vm = b64(json.dumps({"add": "cdn.example.com", "port": "8443", "id": "AAAA-BBBB", "net": "ws"}))
n = parse_link("vmess://" + vm)
check("parsed", n is not None)
check("host lowercased", n and n.host == "cdn.example.com")
check("port int", n and n.port == 8443)
check("garbage -> None", parse_link("vmess://!!!!notb64!!!!") is None)
check("bad json -> None", parse_link("vmess://" + b64("this is not json at all")) is None)
check("missing id -> None", parse_link("vmess://" + b64(json.dumps({"add": "1.2.3.4", "port": 443}))) is None)
check("private add -> None", parse_link("vmess://" + b64(json.dumps({"add": "192.168.0.1", "port": 443, "id": "x"}))) is None)

print("== parse ss ==")
n = parse_link("ss://" + b64("aes-256-gcm:pass123") + "@5.6.7.8:8388#Tokyo")
check("userinfo form", n is not None and n.host == "5.6.7.8" and n.port == 8388)
n2 = parse_link("ss://" + b64("aes-256-gcm:pass123@5.6.7.8:8388") + "#Tokyo")
check("fully-encoded form", n2 is not None and n2.host == "5.6.7.8")
check("same server dedups equal", n and n2 and n.host == n2.host and n.port == n2.port)
check("no @ garbage -> None", parse_link("ss://" + b64("nothing here at all")) is None)

print("== parse trojan / hysteria2 / tuic ==")
check("trojan", (lambda x: x is not None and x.proto == "trojan")(parse_link("trojan://pw@9.9.9.9:443?sni=a.com#T")))
h = parse_link("hy2://pw@9.9.9.9:8443?insecure=1#H")
check("hy2 normalized to hysteria2", h is not None and h.proto == "hysteria2")
check("hysteria2 full name", (lambda x: x is not None and x.proto == "hysteria2")(parse_link("hysteria2://pw@9.9.9.9:8443#H")))
check("tuic", (lambda x: x is not None and x.proto == "tuic")(parse_link("tuic://uuid:pw@9.9.9.9:443#Tu")))

print("== robustness (не должно быть исключений) ==")
junk = [
    "", "   ", "vless://", "vmess://", "ss://", "trojan://", "hysteria2://",
    "://@:", "vless://@:0", "not a link at all", "http://example.com",
    "vless://a@[::1]:443", "ss://@@@@", "vmess://" + "A" * 300,
    "vless://u@1.2.3.4:443?" + "x=1&" * 500,
    "tuic://" + "\x00\x01\x02", "ss://" + "=" * 50,
]
crashed = []
for item in junk:
    try:
        parse_link(item)
    except Exception as exc:
        crashed.append(f"{item[:25]!r} -> {type(exc).__name__}: {exc}")
check("мусор не роняет парсер", not crashed, str(crashed))

print("== extract_links ==")
text = "junk vless://u@1.1.1.1:443#a\nnoise trojan://p@2.2.2.2:443#b\n"
check("из plain-текста", len(extract_links(text)) == 2)
check("из base64", len(extract_links(b64(text))) == 2)
check("из пустоты", extract_links("") == [])
check("не ловит http", extract_links("see http://example.com and https://a.b") == [])

print("== retag ==")
node = Node(raw="vless://u@1.2.3.4:443#OldName", proto="vless", host="1.2.3.4",
            port=443, ident="k", latency_ms=87)
tagged = retag(node, 1)
check("старый тег убран", "OldName" not in tagged)
check("новый тег на месте", "87ms" in tagged)
check("тело ссылки не тронуто", tagged.startswith("vless://u@1.2.3.4:443#"))
check("ровно один #", tagged.count("#") == 1)

print("== дедупликация ==")
a = parse_link("vless://uuid-1@1.2.3.4:443?sni=x.com#name-one")
b = parse_link("vless://uuid-1@1.2.3.4:443?sni=x.com#name-two")
c = parse_link("vless://uuid-1@1.2.3.4:443?sni=other.com#name")
check("разные имена = один узел", a and b and a.key == b.key)
check("разный sni = разные узлы", a and c and a.key != c.key)

print()
if failures:
    print(f"ПРОВАЛЕНО: {len(failures)} -> {failures}")
    sys.exit(1)
print("Все тесты пройдены.")
