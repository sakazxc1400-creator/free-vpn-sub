#!/usr/bin/env python3
"""
Настоящая проверка узлов: поднимаем sing-box и пробуем сходить через каждый
узел в интернет. TCP-коннект показывает только то, что порт открыт, — а через
такой узел трафик может не пойти вообще.

Схема: на каждый узел вешается локальный HTTP-прокси, все узлы поднимаются
одним процессом sing-box, дальше через каждый прокси делается запрос
к generate_204. Ответ 204 = узел рабочий.

Если бинарника sing-box нет, verify() возвращает пустой список, и вызывающая
сторона откатывается на TCP-проверку.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import outbound

# Проверочные адреса. Отвечают 204 с пустым телом.
PROBE_URLS = (
    "http://connectivitycheck.gstatic.com/generate_204",
    "http://cp.cloudflare.com/generate_204",
)

BATCH_SIZE = 80          # узлов на один процесс sing-box
PROBE_TIMEOUT = 8.0      # сек на запрос через узел
PROBE_WORKERS = 40       # параллельных запросов внутри батча
STARTUP_TIMEOUT = 20.0   # сек на подъём sing-box
PORT_BASE = 24000


def log(msg: str) -> None:
    print(msg, flush=True)


def find_singbox() -> str | None:
    """Ищет бинарник sing-box в PATH и рядом с проектом."""
    found = shutil.which("sing-box")
    if found:
        return found
    for candidate in (
        Path(__file__).resolve().parent / "sing-box",
        Path(__file__).resolve().parent / "sing-box.exe",
    ):
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def free_ports(count: int) -> list[int]:
    """Подбирает свободные порты, начиная с PORT_BASE."""
    ports: list[int] = []
    port = PORT_BASE
    while len(ports) < count and port < 65000:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                ports.append(port)
            except OSError:
                pass
        port += 1
    return ports


def build_config(pairs: list[tuple[int, dict]]) -> dict:
    """Собирает конфиг sing-box: по одному HTTP-инбаунду на узел."""
    inbounds = []
    outbounds = []
    rules = []

    for index, (port, node_outbound) in enumerate(pairs):
        in_tag = f"in-{index}"
        out_tag = f"out-{index}"
        inbounds.append({
            "type": "http",
            "tag": in_tag,
            "listen": "127.0.0.1",
            "listen_port": port,
        })
        node_outbound = dict(node_outbound)
        node_outbound["tag"] = out_tag
        outbounds.append(node_outbound)
        rules.append({
            "inbound": [in_tag],
            "action": "route",
            "outbound": out_tag,
        })

    # Всё, что не попало ни в одно правило, отбрасываем: утечки мимо
    # проверяемого узла нам не нужны.
    rules.append({"action": "reject"})

    return {
        "log": {"level": "fatal"},
        # DNS нужен, чтобы разрешать доменные имена самих серверов.
        "dns": {
            "servers": [{
                "type": "udp",
                "tag": "cf",
                "server": "1.1.1.1",
            }],
        },
        "inbounds": inbounds,
        "outbounds": outbounds,
        "route": {
            "rules": rules,
            "default_domain_resolver": {
                "server": "cf",
                "strategy": "prefer_ipv4",
            },
        },
    }


def wait_ready(ports: list[int], deadline: float) -> bool:
    """Ждёт, пока sing-box начнёт слушать порты."""
    probe = ports[: min(5, len(ports))]
    while time.time() < deadline:
        ready = 0
        for port in probe:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    ready += 1
            except OSError:
                break
        if ready == len(probe):
            return True
        time.sleep(0.4)
    return False


def probe_one(port: int) -> int | None:
    """Запрос через локальный прокси. Возвращает задержку в мс или None."""
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({
            "http": f"http://127.0.0.1:{port}",
            "https": f"http://127.0.0.1:{port}",
        }),
        urllib.request.HTTPSHandler(),
    )
    for url in PROBE_URLS:
        start = time.perf_counter()
        try:
            with opener.open(url, timeout=PROBE_TIMEOUT) as resp:
                if resp.status in (200, 204):
                    body = resp.read(64)
                    # generate_204 обязан вернуть пустое тело. Непустой ответ —
                    # это подстановка провайдера или заглушка, узел не годится.
                    if resp.status == 204 and body:
                        continue
                    return int((time.perf_counter() - start) * 1000)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                ValueError, TimeoutError):
            continue
    return None


def verify_batch(nodes: list, singbox: str) -> list[tuple[object, int]]:
    """Проверяет один батч узлов. Возвращает пары (узел, задержка_мс)."""
    prepared: list[tuple[object, dict]] = []
    for node in nodes:
        built = outbound.build(node.raw)
        if built is not None:
            prepared.append((node, built))
    if not prepared:
        return []

    ports = free_ports(len(prepared))
    if len(ports) < len(prepared):
        prepared = prepared[: len(ports)]
    pairs = [(ports[i], cfg) for i, (_, cfg) in enumerate(prepared)]

    config = build_config(pairs)
    tmp = tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    )
    try:
        json.dump(config, tmp)
        tmp.close()

        proc = subprocess.Popen(
            [singbox, "run", "-c", tmp.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            if not wait_ready(ports, time.time() + STARTUP_TIMEOUT):
                proc.terminate()
                err = b""
                try:
                    _, err = proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                tail = err.decode("utf-8", "ignore").strip().splitlines()[-2:]
                log(f"    sing-box не поднялся: {' | '.join(tail) or 'нет вывода'}")
                return []

            results: list[tuple[object, int]] = []
            with ThreadPoolExecutor(max_workers=PROBE_WORKERS) as pool:
                futures = {
                    pool.submit(probe_one, ports[i]): prepared[i][0]
                    for i in range(len(prepared))
                }
                for fut in as_completed(futures):
                    node = futures[fut]
                    try:
                        latency = fut.result()
                    except Exception:
                        continue
                    if latency is not None:
                        results.append((node, latency))
            return results
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def verify(nodes: list, need: int) -> list[tuple[object, int]]:
    """
    Проверяет узлы батчами, пока не наберётся need рабочих.
    Возвращает пары (узел, задержка_мс), отсортированные по задержке.
    """
    singbox = find_singbox()
    if not singbox:
        log("    sing-box не найден — настоящая проверка пропущена")
        return []

    version = "?"
    try:
        out = subprocess.run(
            [singbox, "version"], capture_output=True, text=True, timeout=15
        )
        version = (out.stdout or out.stderr).strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        pass
    log(f"    {version}")

    good: list[tuple[object, int]] = []
    checked = 0

    for start in range(0, len(nodes), BATCH_SIZE):
        batch = nodes[start:start + BATCH_SIZE]
        good.extend(verify_batch(batch, singbox))
        checked += len(batch)
        log(f"    проверено {checked}/{len(nodes)}, рабочих {len(good)}")
        if len(good) >= need:
            break

    good.sort(key=lambda pair: pair[1])
    return good


if __name__ == "__main__":
    path = find_singbox()
    print(f"sing-box: {path or 'не найден'}")
    sys.exit(0 if path else 1)
