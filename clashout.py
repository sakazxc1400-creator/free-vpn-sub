#!/usr/bin/env python3
"""Узлы в конфиг Clash/Mihomo через outbound.py."""

from __future__ import annotations

import json

import outbound

# по этому адресу Clash ищет быстрейший узел в группе "Авто"
DEFAULT_TEST_URL = "http://cp.cloudflare.com/generate_204"

# страна попадает в группы, только если узлов хватает
MIN_COUNTRY_GROUP = 5
MAX_COUNTRY_GROUPS = 10

# в Clash значения VMess другие, не как в ссылке
VMESS_CIPHER = {
    "auto": "auto",
    "zero": "none",
    "none": "none",
    "aes-128-gcm": "aes-128-gcm",
    "chacha20-poly1305": "chacha20-poly1305",
}


def _scalar(value: object) -> str:
    """Скаляр в виде YAML, строки всегда в кавычках."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _yaml_lines(value: object, indent: int = 0) -> list[str]:
    pad = " " * indent
    lines: list[str] = []

    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{pad}{key}:")
                lines.extend(_yaml_lines(item, indent + 2))
            elif isinstance(item, (dict, list)):
                lines.append(f"{pad}{key}: " + ("{}" if isinstance(item, dict) else "[]"))
            else:
                lines.append(f"{pad}{key}: {_scalar(item)}")
        return lines

    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item:
                first = True
                for key, sub in item.items():
                    prefix = "- " if first else "  "
                    if isinstance(sub, dict | list) and sub:
                        lines.append(f"{pad}{prefix}{key}:")
                        lines.extend(_yaml_lines(sub, indent + 4))
                    elif isinstance(sub, dict | list):
                        lines.append(
                            f"{pad}{prefix}{key}: "
                            + ("{}" if isinstance(sub, dict) else "[]")
                        )
                    else:
                        lines.append(f"{pad}{prefix}{key}: {_scalar(sub)}")
                    first = False
            elif isinstance(item, (dict, list)):
                lines.append(f"{pad}- " + ("{}" if isinstance(item, dict) else "[]"))
            else:
                lines.append(f"{pad}- {_scalar(item)}")
        return lines

    return [f"{pad}{_scalar(value)}"]


def yaml_dump(value: object) -> str:
    return "\n".join(_yaml_lines(value)) + "\n"


def _tls(proxy: dict, out: dict, key: str = "servername") -> None:
    """TLS-блок; key: у trojan это sni, у vless servername."""
    tls = out.get("tls") or {}
    if not tls.get("enabled"):
        return

    proxy["tls"] = True
    if tls.get("server_name"):
        proxy[key] = tls["server_name"]
    if tls.get("insecure"):
        proxy["skip-cert-verify"] = True
    if tls.get("alpn"):
        proxy["alpn"] = list(tls["alpn"])
    fingerprint = (tls.get("utls") or {}).get("fingerprint")
    if fingerprint:
        proxy["client-fingerprint"] = fingerprint

    reality = tls.get("reality") or {}
    if reality.get("public_key"):
        proxy["reality-opts"] = {"public-key": reality["public_key"]}
        if reality.get("short_id"):
            proxy["reality-opts"]["short-id"] = reality["short_id"]


def _transport(proxy: dict, out: dict) -> None:
    transport = out.get("transport") or {}
    kind = str(transport.get("type", "tcp"))
    path = transport.get("path")

    if kind == "ws":
        proxy["network"] = "ws"
        opts: dict = {}
        if path:
            opts["path"] = path
        host = (transport.get("headers") or {}).get("Host")
        if host:
            opts["headers"] = {"Host": host}
        if opts:
            proxy["ws-opts"] = opts
        return

    if kind == "grpc":
        proxy["network"] = "grpc"
        if transport.get("service_name"):
            proxy["grpc-opts"] = {"grpc-service-name": transport["service_name"]}
        return

    if kind == "http":
        proxy["network"] = "h2"
        opts = {}
        if transport.get("host"):
            opts["host"] = list(transport["host"])
        if path:
            opts["path"] = path
        if opts:
            proxy["h2-opts"] = opts
        return

    if kind == "httpupgrade":
        # в Clash это ws поверх http-upgrade
        proxy["network"] = "ws"
        opts = {"v2ray-http-upgrade": True}
        if path:
            opts["path"] = path
        if transport.get("host"):
            opts["headers"] = {"Host": transport["host"]}
        proxy["ws-opts"] = opts
        return

    proxy["network"] = "tcp"


def _from_vless(out: dict) -> dict:
    proxy: dict = {
        "type": "vless",
        "server": out["server"],
        "port": out["server_port"],
        "uuid": out["uuid"],
        "udp": True,
    }
    if out.get("flow"):
        proxy["flow"] = out["flow"]
    _tls(proxy, out)
    _transport(proxy, out)
    return proxy


def _from_vmess(out: dict) -> dict:
    cipher = str(out.get("security", "auto")).lower()
    proxy: dict = {
        "type": "vmess",
        "server": out["server"],
        "port": out["server_port"],
        "uuid": out["uuid"],
        "alterId": int(out.get("alter_id", 0) or 0),
        "cipher": VMESS_CIPHER.get(cipher, "auto"),
        "udp": True,
    }
    _tls(proxy, out)
    _transport(proxy, out)
    return proxy


def _from_trojan(out: dict) -> dict:
    proxy: dict = {
        "type": "trojan",
        "server": out["server"],
        "port": out["server_port"],
        "password": out["password"],
        "udp": True,
    }
    _tls(proxy, out, key="sni")
    _transport(proxy, out)
    return proxy


def _from_ss(out: dict) -> dict:
    return {
        "type": "ss",
        "server": out["server"],
        "port": out["server_port"],
        "cipher": out["method"],
        "password": out["password"],
        "udp": True,
    }


def _from_hysteria2(out: dict) -> dict:
    proxy: dict = {
        "type": "hysteria2",
        "server": out["server"],
        "port": out["server_port"],
        "password": out["password"],
    }
    tls = out.get("tls") or {}
    if tls.get("server_name"):
        proxy["sni"] = tls["server_name"]
    if tls.get("insecure"):
        proxy["skip-cert-verify"] = True
    if tls.get("alpn"):
        proxy["alpn"] = list(tls["alpn"])
    obfs = out.get("obfs") or {}
    if obfs.get("password"):
        proxy["obfs"] = str(obfs.get("type", "salamander"))
        proxy["obfs-password"] = obfs["password"]
    return proxy


def _from_tuic(out: dict) -> dict:
    # пустой пароль Clash не принимает
    if not out.get("password"):
        raise ValueError("пустой пароль")
    proxy: dict = {
        "type": "tuic",
        "server": out["server"],
        "port": out["server_port"],
        "uuid": out["uuid"],
        "password": out["password"],
    }
    tls = out.get("tls") or {}
    if tls.get("server_name"):
        proxy["sni"] = tls["server_name"]
    if tls.get("insecure"):
        proxy["skip-cert-verify"] = True
    if tls.get("alpn"):
        proxy["alpn"] = list(tls["alpn"])
    if out.get("congestion_control"):
        proxy["congestion-controller"] = out["congestion_control"]
    if out.get("udp_relay_mode"):
        proxy["udp-relay-mode"] = out["udp_relay_mode"]
    return proxy


CLASH_BUILDERS = {
    "vless": _from_vless,
    "vmess": _from_vmess,
    "trojan": _from_trojan,
    "shadowsocks": _from_ss,
    "hysteria2": _from_hysteria2,
    "tuic": _from_tuic,
}


def _fallback_name(node: object) -> str:
    country = str(getattr(node, "country", "") or "??")
    proto = str(getattr(node, "proto", "") or "node")
    latency = getattr(node, "latency_ms", None)
    if latency:
        return f"{country} · {proto} · {latency}ms"
    return f"{country} · {proto}"


def _unique(name: str, used: dict[str, int]) -> str:
    name = name.strip() or "node"
    if name not in used:
        used[name] = 1
        return name
    used[name] += 1
    return f"{name} #{used[name]}"


def clash_proxy(node: object) -> dict | None:
    raw = getattr(node, "raw", None)
    if not raw:
        return None

    out = outbound.build(str(raw))
    if not out:
        return None

    builder = CLASH_BUILDERS.get(str(out.get("type", "")))
    if builder is None:
        return None

    try:
        proxy = builder(out)
    except (KeyError, TypeError, ValueError):
        return None

    if not proxy.get("server") or not proxy.get("port"):
        return None
    return {"name": _fallback_name(node), **proxy}


def _country_groups(names: list[str], countries: list[str]) -> list[dict]:
    counts: dict[str, int] = {}
    for code in countries:
        if code:
            counts[code] = counts.get(code, 0) + 1

    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    groups: list[dict] = []
    for code, count in ordered[:MAX_COUNTRY_GROUPS]:
        if count < MIN_COUNTRY_GROUP:
            break
        members = [name for name, cc in zip(names, countries) if cc == code]
        groups.append({"name": code, "type": "select", "proxies": members})
    return groups


def build_clash(
    nodes: list,
    labels: list[str] | None = None,
    test_url: str = DEFAULT_TEST_URL,
) -> str:
    """Список узлов -> текст конфига Clash/Mihomo."""
    proxies: list[dict] = []
    countries: list[str] = []
    used: dict[str, int] = {}

    for index, node in enumerate(nodes):
        proxy = clash_proxy(node)
        if proxy is None:
            continue

        name = proxy["name"]
        if labels is not None and index < len(labels):
            name = str(labels[index]).strip() or name
        proxy["name"] = _unique(name, used)

        proxies.append(proxy)
        countries.append(str(getattr(node, "country", "") or ""))

    names = [proxy["name"] for proxy in proxies]

    groups: list[dict] = []
    if names:
        groups.append({
            "name": "Авто",
            "type": "url-test",
            "url": test_url,
            "interval": 300,
            "tolerance": 50,
            "proxies": names,
        })
        groups.append({"name": "Ручной", "type": "select", "proxies": names})
        groups.extend(_country_groups(names, countries))

    rules = [
        "DOMAIN-SUFFIX,local,DIRECT",
        "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
        "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
        "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
        "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
        "MATCH,Авто" if names else "MATCH,DIRECT",
    ]

    config = {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "proxies": proxies,
        "proxy-groups": groups,
        "rules": rules,
    }

    header = (
        "# Подписка free-vpn-sub: "
        "https://github.com/sakazxc1400-creator/free-vpn-sub\n"
        "# Формат Clash / Mihomo, узлы проверены на живой трафик.\n"
    )
    return header + yaml_dump(config)
