#!/usr/bin/env python3
"""
Преобразование share-ссылок (vless://, vmess://, ...) в outbound-конфиг sing-box.

Нужно для настоящей проверки узлов: чтобы понять, работает сервер или нет,
через него надо реально сходить в интернет, а не просто постучать в порт.

Всё, что sing-box не умеет (kcp, quic-транспорт, xhttp, ss с плагинами),
отбрасывается — такой узел мы просто не проверяем и не публикуем.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import urllib.parse

# Шифры shadowsocks, которые понимает sing-box.
SS_METHODS = {
    "aes-128-gcm", "aes-192-gcm", "aes-256-gcm",
    "chacha20-ietf-poly1305", "xchacha20-ietf-poly1305",
    "2022-blake3-aes-128-gcm", "2022-blake3-aes-256-gcm",
    "2022-blake3-chacha20-poly1305",
    "none",
}

# Транспорты, которые мы умеем описать.
NET_WS = {"ws", "websocket"}
NET_GRPC = {"grpc", "gun"}
NET_HTTP = {"h2", "http", "h2mux"}
NET_UPGRADE = {"httpupgrade"}
NET_PLAIN = {"tcp", "raw", "", "none"}


def _b64(data: str) -> str | None:
    cleaned = re.sub(r"\s+", "", data).replace("-", "+").replace("_", "/")
    if not cleaned:
        return None
    cleaned += "=" * (-len(cleaned) % 4)
    try:
        return base64.b64decode(cleaned, validate=False).decode("utf-8", "ignore")
    except (binascii.Error, ValueError):
        return None


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _alpn(value: str | None) -> list[str]:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


def _first(params: dict[str, list[str]], *names: str, default: str = "") -> str:
    for name in names:
        if name in params and params[name]:
            value = params[name][0]
            if value:
                return value
    return default


def _tls_block(
    *,
    enabled: bool,
    sni: str,
    insecure: bool,
    alpn: list[str],
    fingerprint: str = "",
    public_key: str = "",
    short_id: str = "",
) -> dict | None:
    if not enabled:
        return None
    tls: dict = {"enabled": True}
    if sni:
        tls["server_name"] = sni
    if insecure:
        tls["insecure"] = True
    if alpn:
        tls["alpn"] = alpn
    if fingerprint:
        tls["utls"] = {"enabled": True, "fingerprint": fingerprint}
    if public_key:
        tls["reality"] = {"enabled": True, "public_key": public_key}
        if short_id:
            tls["reality"]["short_id"] = short_id
        # Reality всегда требует uTLS.
        tls.setdefault("utls", {"enabled": True, "fingerprint": "chrome"})
    return tls


def _transport_block(
    net: str, *, path: str, host: str, service_name: str, header_type: str
) -> dict | None | bool:
    """
    Возвращает transport-блок, None (транспорт не нужен)
    или False (транспорт не поддерживается, узел пропускаем).
    """
    net = (net or "tcp").strip().lower()

    if net in NET_WS:
        block: dict = {"type": "ws"}
        if path:
            block["path"] = path
        if host:
            block["headers"] = {"Host": host}
        return block

    if net in NET_GRPC:
        return {"type": "grpc", "service_name": service_name or path.lstrip("/")}

    if net in NET_HTTP:
        block = {"type": "http"}
        if host:
            block["host"] = [host]
        if path:
            block["path"] = path
        return block

    if net in NET_UPGRADE:
        block = {"type": "httpupgrade"}
        if host:
            block["host"] = host
        if path:
            block["path"] = path
        return block

    if net in NET_PLAIN:
        # tcp с http-обфускацией описывается как http-транспорт.
        if (header_type or "").lower() == "http":
            block = {"type": "http"}
            if host:
                block["host"] = [host]
            if path:
                block["path"] = path
            return block
        return None

    return False


def _from_vless(link: str) -> dict | None:
    parsed = urllib.parse.urlsplit(link)
    params = urllib.parse.parse_qs(parsed.query)

    uuid = urllib.parse.unquote(parsed.username or "")
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if not uuid or not host or not port:
        return None

    security = _first(params, "security").lower()
    sni = _first(params, "sni", "peer", "host")
    public_key = _first(params, "pbk", "publicKey")
    net = _first(params, "type", "net", default="tcp")

    transport = _transport_block(
        net,
        path=urllib.parse.unquote(_first(params, "path")),
        host=_first(params, "host"),
        service_name=_first(params, "serviceName"),
        header_type=_first(params, "headerType"),
    )
    if transport is False:
        return None

    out: dict = {
        "type": "vless",
        "server": host,
        "server_port": port,
        "uuid": uuid,
    }

    flow = _first(params, "flow")
    if flow == "xtls-rprx-vision":
        out["flow"] = flow

    tls = _tls_block(
        enabled=security in ("tls", "reality", "xtls") or bool(public_key),
        sni=sni,
        insecure=_truthy(_first(params, "allowInsecure", "insecure")),
        alpn=_alpn(_first(params, "alpn")),
        fingerprint=_first(params, "fp"),
        public_key=public_key,
        short_id=_first(params, "sid", "shortId"),
    )
    if tls:
        out["tls"] = tls
    if transport:
        out["transport"] = transport
    return out


def _from_vmess(link: str) -> dict | None:
    decoded = _b64(link[len("vmess://"):])
    if not decoded:
        return None
    try:
        cfg = json.loads(decoded)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(cfg, dict):
        return None

    host = str(cfg.get("add", "")).strip().lower()
    uuid = str(cfg.get("id", "")).strip()
    try:
        port = int(str(cfg.get("port", "")).strip())
    except (TypeError, ValueError):
        return None
    if not host or not uuid or not 0 < port < 65536:
        return None

    transport = _transport_block(
        str(cfg.get("net", "tcp")),
        path=str(cfg.get("path", "")),
        host=str(cfg.get("host", "")),
        service_name=str(cfg.get("path", "")).lstrip("/"),
        header_type=str(cfg.get("type", "")),
    )
    if transport is False:
        return None

    try:
        alter_id = int(str(cfg.get("aid", cfg.get("alterId", 0)) or 0))
    except (TypeError, ValueError):
        alter_id = 0

    cipher = str(cfg.get("scy", cfg.get("security", "auto")) or "auto").lower()
    if cipher in ("", "auto", "none"):
        cipher = "auto"

    out: dict = {
        "type": "vmess",
        "server": host,
        "server_port": port,
        "uuid": uuid,
        "security": cipher,
        "alter_id": alter_id,
    }

    tls_on = str(cfg.get("tls", "")).lower() in ("tls", "reality", "true", "1")
    tls = _tls_block(
        enabled=tls_on,
        sni=str(cfg.get("sni", "") or cfg.get("host", "")),
        insecure=_truthy(cfg.get("allowInsecure", cfg.get("verify_cert") is False)),
        alpn=_alpn(str(cfg.get("alpn", ""))),
        fingerprint=str(cfg.get("fp", "")),
    )
    if tls:
        out["tls"] = tls
    if transport:
        out["transport"] = transport
    return out


def _from_trojan(link: str) -> dict | None:
    parsed = urllib.parse.urlsplit(link)
    params = urllib.parse.parse_qs(parsed.query)

    password = urllib.parse.unquote(parsed.username or "")
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if not password or not host or not port:
        return None

    transport = _transport_block(
        _first(params, "type", "net", default="tcp"),
        path=urllib.parse.unquote(_first(params, "path")),
        host=_first(params, "host"),
        service_name=_first(params, "serviceName"),
        header_type=_first(params, "headerType"),
    )
    if transport is False:
        return None

    out: dict = {
        "type": "trojan",
        "server": host,
        "server_port": port,
        "password": password,
    }
    tls = _tls_block(
        enabled=True,
        sni=_first(params, "sni", "peer", "host"),
        insecure=_truthy(_first(params, "allowInsecure", "insecure")),
        alpn=_alpn(_first(params, "alpn")),
        fingerprint=_first(params, "fp"),
    )
    if tls:
        out["tls"] = tls
    if transport:
        out["transport"] = transport
    return out


def _from_ss(link: str) -> dict | None:
    body = link[len("ss://"):].split("#", 1)[0]
    query = ""
    if "?" in body:
        body, query = body.split("?", 1)
    if "plugin=" in query:
        return None  # плагины (obfs, v2ray-plugin) не разбираем

    if "@" in body:
        creds, _, endpoint = body.rpartition("@")
        decoded_creds = _b64(creds) or urllib.parse.unquote(creds)
    else:
        decoded = _b64(body)
        if not decoded or "@" not in decoded:
            return None
        decoded_creds, _, endpoint = decoded.rpartition("@")

    if ":" not in decoded_creds or ":" not in endpoint:
        return None

    method, _, password = decoded_creds.partition(":")
    method = method.strip().lower()
    if method not in SS_METHODS:
        return None

    host, _, port_str = endpoint.strip().strip("/").rpartition(":")
    host = host.strip("[]").lower()
    try:
        port = int(port_str)
    except (TypeError, ValueError):
        return None
    if not host or not 0 < port < 65536:
        return None

    return {
        "type": "shadowsocks",
        "server": host,
        "server_port": port,
        "method": method,
        "password": password,
    }


def _from_hysteria2(link: str) -> dict | None:
    parsed = urllib.parse.urlsplit(link)
    params = urllib.parse.parse_qs(parsed.query)

    host = (parsed.hostname or "").lower()
    port = parsed.port
    if not host or not port:
        return None

    password = urllib.parse.unquote(parsed.username or "")
    if parsed.password:
        password = f"{password}:{urllib.parse.unquote(parsed.password)}"
    if not password:
        return None

    out: dict = {
        "type": "hysteria2",
        "server": host,
        "server_port": port,
        "password": password,
    }

    obfs_pw = _first(params, "obfs-password", "obfsParam")
    if _first(params, "obfs").lower() == "salamander" and obfs_pw:
        out["obfs"] = {"type": "salamander", "password": obfs_pw}

    tls = _tls_block(
        enabled=True,
        sni=_first(params, "sni", "peer"),
        insecure=_truthy(_first(params, "insecure", "allowInsecure")),
        alpn=_alpn(_first(params, "alpn")) or ["h3"],
    )
    out["tls"] = tls
    return out


def _from_tuic(link: str) -> dict | None:
    parsed = urllib.parse.urlsplit(link)
    params = urllib.parse.parse_qs(parsed.query)

    host = (parsed.hostname or "").lower()
    port = parsed.port
    uuid = urllib.parse.unquote(parsed.username or "")
    if not host or not port or not uuid:
        return None

    out: dict = {
        "type": "tuic",
        "server": host,
        "server_port": port,
        "uuid": uuid,
        "password": urllib.parse.unquote(parsed.password or ""),
        "congestion_control": _first(
            params, "congestion_control", "congestion", default="bbr"
        ),
        "udp_relay_mode": _first(params, "udp_relay_mode", default="native"),
    }
    out["tls"] = _tls_block(
        enabled=True,
        sni=_first(params, "sni", "peer"),
        insecure=_truthy(_first(params, "insecure", "allow_insecure")),
        alpn=_alpn(_first(params, "alpn")) or ["h3"],
    )
    return out


_BUILDERS = {
    "vless": _from_vless,
    "vmess": _from_vmess,
    "trojan": _from_trojan,
    "ss": _from_ss,
    "hysteria2": _from_hysteria2,
    "hy2": _from_hysteria2,
    "tuic": _from_tuic,
}


def build(link: str) -> dict | None:
    """Ссылка -> outbound sing-box (без тега). None, если не поддерживается."""
    link = link.strip()
    scheme = link.split("://", 1)[0].lower() if "://" in link else ""
    builder = _BUILDERS.get(scheme)
    if builder is None:
        return None
    try:
        return builder(link)
    except Exception:
        return None
