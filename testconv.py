#!/usr/bin/env python3
"""
Тесты конвертера ссылок в outbound sing-box и логики geo/отбора.
Сеть не нужна.  Запуск:  py testconv.py
"""

import json
import sys
from base64 import b64encode

import collect
import geo
import outbound
from collect import Node

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [ok] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")
        failures.append(name)


def b64(s: str) -> str:
    return b64encode(s.encode()).decode()


print("== outbound: vless ==")
o = outbound.build(
    "vless://11111111-2222-3333-4444-555555555555@1.2.3.4:443"
    "?type=ws&security=tls&sni=a.com&path=%2Fws&host=b.com&fp=chrome#n"
)
check("собран", o is not None)
check("type", o and o["type"] == "vless")
check("server/port", o and o["server"] == "1.2.3.4" and o["server_port"] == 443)
check("uuid", o and o["uuid"].startswith("11111111"))
check("tls вкл", o and o["tls"]["enabled"] is True)
check("sni", o and o["tls"]["server_name"] == "a.com")
check("utls", o and o["tls"]["utls"]["fingerprint"] == "chrome")
check("ws transport", o and o["transport"]["type"] == "ws")
check("ws path", o and o["transport"]["path"] == "/ws")
check("ws Host", o and o["transport"]["headers"]["Host"] == "b.com")

print("== outbound: vless reality ==")
o = outbound.build(
    "vless://aaaa-bbbb@5.6.7.8:443?security=reality&pbk=PUBKEY123&sid=ab"
    "&sni=ya.ru&flow=xtls-rprx-vision&type=tcp#r"
)
check("reality вкл", o and o["tls"]["reality"]["enabled"] is True)
check("public_key", o and o["tls"]["reality"]["public_key"] == "PUBKEY123")
check("short_id", o and o["tls"]["reality"]["short_id"] == "ab")
check("flow", o and o.get("flow") == "xtls-rprx-vision")
check("utls автодобавлен", o and "utls" in o["tls"])
check("tcp без transport", o and "transport" not in o)

print("== outbound: vless grpc ==")
o = outbound.build("vless://u1@9.9.9.9:443?type=grpc&serviceName=svc&security=tls#g")
check("grpc", o and o["transport"]["type"] == "grpc")
check("service_name", o and o["transport"]["service_name"] == "svc")

print("== outbound: неподдерживаемый транспорт ==")
check("kcp -> None", outbound.build("vless://u@1.1.1.1:443?type=kcp#k") is None)
check("xhttp -> None", outbound.build("vless://u@1.1.1.1:443?type=xhttp#x") is None)

print("== outbound: vmess ==")
cfg = {"add": "3.3.3.3", "port": "8443", "id": "vm-uuid", "aid": "2",
       "net": "ws", "path": "/p", "host": "h.com", "tls": "tls", "scy": "auto"}
o = outbound.build("vmess://" + b64(json.dumps(cfg)))
check("собран", o is not None)
check("alter_id int", o and o["alter_id"] == 2)
check("security", o and o["security"] == "auto")
check("tls", o and o["tls"]["enabled"] is True)
check("ws path", o and o["transport"]["path"] == "/p")
check("порт строкой -> int", o and o["server_port"] == 8443)

cfg_notls = {"add": "4.4.4.4", "port": 80, "id": "x", "net": "tcp"}
o = outbound.build("vmess://" + b64(json.dumps(cfg_notls)))
check("без tls нет блока", o and "tls" not in o)
check("aid по умолчанию 0", o and o["alter_id"] == 0)

print("== outbound: trojan ==")
o = outbound.build("trojan://pw123@7.7.7.7:443?sni=t.com&allowInsecure=1#t")
check("собран", o is not None)
check("password", o and o["password"] == "pw123")
check("tls всегда", o and o["tls"]["enabled"] is True)
check("insecure", o and o["tls"]["insecure"] is True)

print("== outbound: shadowsocks ==")
o = outbound.build("ss://" + b64("aes-256-gcm:secret") + "@8.8.8.8:8388#s")
check("собран", o is not None)
check("method", o and o["method"] == "aes-256-gcm")
check("password", o and o["password"] == "secret")
o2 = outbound.build("ss://" + b64("chacha20-ietf-poly1305:p@8.8.8.8:1234"))
check("полностью закодированный", o2 and o2["server_port"] == 1234)
check("неизвестный шифр -> None",
      outbound.build("ss://" + b64("rc4-md5:p") + "@1.1.1.1:1#x") is None)
check("плагин -> None",
      outbound.build("ss://" + b64("aes-256-gcm:p") + "@1.1.1.1:1?plugin=obfs#x") is None)

print("== outbound: hysteria2 / tuic ==")
o = outbound.build("hy2://pass@6.6.6.6:8443?insecure=1&sni=h.com"
                   "&obfs=salamander&obfs-password=op#h")
check("hysteria2", o and o["type"] == "hysteria2")
check("obfs", o and o["obfs"]["type"] == "salamander")
check("obfs pw", o and o["obfs"]["password"] == "op")
check("alpn h3", o and o["tls"]["alpn"] == ["h3"])

o = outbound.build("tuic://uuid-x:pw-y@2.2.2.2:443?congestion_control=bbr#tu")
check("tuic", o and o["type"] == "tuic")
check("uuid", o and o["uuid"] == "uuid-x")
check("password", o and o["password"] == "pw-y")

print("== outbound: устойчивость ==")
junk = ["", "vless://", "vmess://", "ss://", "trojan://", "hy2://", "tuic://",
        "vless://@:", "vmess://!!!", "ss://@@@", "http://x.com",
        "vless://u@1.1.1.1", "vless://u@1.1.1.1:99999",
        "vmess://" + b64("[]"), "vmess://" + b64('{"add":"x"}')]
crashed = []
for item in junk:
    try:
        outbound.build(item)
    except Exception as exc:
        crashed.append(f"{item[:20]!r}: {type(exc).__name__}")
check("мусор не роняет конвертер", not crashed, str(crashed))
check("все возвращают None или dict",
      all(outbound.build(j) is None or isinstance(outbound.build(j), dict)
          for j in junk))

print("== geo: флаги и названия ==")
check("NL -> флаг", geo.flag("NL") == "\U0001F1F3\U0001F1F1")
check("US -> флаг", geo.flag("us") == "\U0001F1FA\U0001F1F8")
check("мусор -> чёрный флаг", geo.flag("XYZ") == "\U0001F3F4")
check("пусто -> чёрный флаг", geo.flag("") == "\U0001F3F4")
check("NL -> Нидерланды", geo.country_name("NL") == "Нидерланды")
check("неизвестный -> код", geo.country_name("ZZ") == "ZZ")
check("пусто -> ??", geo.country_name("") == "??")

print("== geo: кэш ==")
import tempfile

_orig_cache = geo.CACHE_FILE
try:
    tmpdir = tempfile.mkdtemp()
    geo.CACHE_FILE = __import__("pathlib").Path(tmpdir) / "cache.json"
    geo.save_cache({"a.com": "NL", "b.com": "DE"})
    loaded = geo.load_cache()
    check("кэш сохраняется и читается", loaded == {"a.com": "NL", "b.com": "DE"},
          str(loaded))

    geo.CACHE_FILE.write_text("{ битый json", encoding="utf-8")
    check("битый кэш -> пусто", geo.load_cache() == {})

    geo.CACHE_FILE.write_text(
        json.dumps({"saved_at": 0, "entries": {"x": "NL"}}), encoding="utf-8"
    )
    check("просроченный кэш -> пусто", geo.load_cache() == {})

    geo.CACHE_FILE.unlink()
    check("нет файла -> пусто", geo.load_cache() == {})
finally:
    geo.CACHE_FILE = _orig_cache

print("== geo: lookup_csv на подставной таблице ==")
_orig_table = geo._csv_table
_orig_tried = geo._csv_tried
try:
    # 10.0.0.0-10.0.0.255 = NL, 20.0.0.0-20.0.0.255 = DE
    geo._csv_table = (
        [167772160, 335544320],
        [167772415, 335544575],
        ["NL", "DE"],
    )
    geo._csv_tried = True
    check("в первом диапазоне", geo.lookup_csv(["10.0.0.5"]) == {"10.0.0.5": "NL"})
    check("во втором диапазоне", geo.lookup_csv(["20.0.0.9"]) == {"20.0.0.9": "DE"})
    check("нижняя граница", geo.lookup_csv(["10.0.0.0"]) == {"10.0.0.0": "NL"})
    check("верхняя граница", geo.lookup_csv(["10.0.0.255"]) == {"10.0.0.255": "NL"})
    check("между диапазонами -> пусто", geo.lookup_csv(["15.0.0.1"]) == {})
    check("до первого -> пусто", geo.lookup_csv(["1.0.0.1"]) == {})
    check("после последнего -> пусто", geo.lookup_csv(["30.0.0.1"]) == {})
    check("мусор не падает", geo.lookup_csv(["", "abc", "1.2.3", "::1"]) == {})
finally:
    geo._csv_table = _orig_table
    geo._csv_tried = _orig_tried

print("== retag: страна в названии ==")
n = Node(raw="vless://u@1.2.3.4:443#Old", proto="vless", host="1.2.3.4",
         port=443, ident="k", latency_ms=84, country="NL")
tag = collect.retag(n, 1)
decoded = __import__("urllib.parse", fromlist=["unquote"]).unquote(tag.split("#")[1])
check("старое имя убрано", "Old" not in tag)
check("флаг в названии", "\U0001F1F3\U0001F1F1" in decoded, decoded)
check("страна словами", "Нидерланды" in decoded, decoded)
check("протокол", "vless" in decoded)
check("задержка", "84ms" in decoded)
check("номер", decoded.startswith("01."), decoded)
check("ровно один #", tag.count("#") == 1)

n2 = Node(raw="hy2://p@1.1.1.1:443#x", proto="hysteria2", host="1.1.1.1",
          port=443, ident="k2", latency_ms=None, country="")
d2 = __import__("urllib.parse", fromlist=["unquote"]).unquote(
    collect.retag(n2, 2).split("#")[1])
check("без страны — чёрный флаг", "\U0001F3F4" in d2, d2)
check("без latency нет 'None'", "None" not in d2, d2)

print("== pick_diverse: квота на страну ==")
nodes = ([Node(raw=f"vless://u@1.0.0.{i}:443", proto="vless", host=f"1.0.0.{i}",
               port=443, ident=str(i), latency_ms=i, country="NL")
          for i in range(20)]
         + [Node(raw=f"vless://u@2.0.0.{i}:443", proto="vless", host=f"2.0.0.{i}",
                 port=443, ident=f"b{i}", latency_ms=100 + i, country="DE")
            for i in range(20)])
picked = collect.pick_diverse(nodes, limit=10, per_country=3)
check("лимит соблюдён", len(picked) == 10)
nl = sum(1 for n in picked if n.country == "NL")
de = sum(1 for n in picked if n.country == "DE")
check("страны сбалансированы", nl == 5 and de == 5, f"nl={nl} de={de}")
check("самый быстрый первым", picked[0].latency_ms == 0)
check("чередование стран", picked[0].country != picked[1].country,
      f"{picked[0].country},{picked[1].country}")

picked2 = collect.pick_diverse(nodes, limit=40, per_country=3)
check("если квоты мало — потолок поднимается", len(picked2) == 40)

picked3 = collect.pick_diverse(nodes, limit=100, per_country=3)
check("больше узлов, чем есть, не выдумывает", len(picked3) == 40)

single = [Node(raw="x", proto="vless", host="h", port=1, ident=str(i),
               latency_ms=i, country="RU") for i in range(5)]
check("одна страна не блокирует набор",
      len(collect.pick_diverse(single, limit=5, per_country=2)) == 5)
check("пустой вход", collect.pick_diverse([], limit=10, per_country=3) == [])
check("limit=0", collect.pick_diverse(nodes, limit=0, per_country=3) == [])

print("== interleave: смешивание протоколов ==")
mixed = collect.interleave(
    [Node(raw="a", proto="vless", host="h", port=1, ident=f"v{i}") for i in range(5)],
    [Node(raw="b", proto="hysteria2", host="h", port=1, ident=f"h{i}") for i in range(2)],
)
check("ничего не потеряно", len(mixed) == 7)
check("hysteria2 не в самом конце",
      any(n.proto == "hysteria2" for n in mixed[:4]),
      str([n.proto for n in mixed]))

print()
if failures:
    print(f"ПРОВАЛЕНО: {len(failures)} -> {failures}")
    sys.exit(1)
print("Все тесты пройдены.")
