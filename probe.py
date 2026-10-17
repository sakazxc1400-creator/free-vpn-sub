#!/usr/bin/env python3
"""
Настоящая проверка узлов: поднимаем sing-box и пробуем сходить через каждый
узел в интернет. TCP-коннект показывает только то, что порт открыт, — а через
такой узел трафик может не пойти вообще.

Схема: на каждый узел вешается локальный HTTP-прокси, все узлы поднимаются
одним процессом sing-box, дальше через каждый прокси делается запрос
к generate_204. Ответ 204 = узел рабочий.

Дополнительно каждый рабочий узел проверяется по HTTPS с полной проверкой
сертификата. Это ловит узлы, которые подменяют сертификаты и читают трафик:
свой сертификат такую проверку не проходит. Результат пишется в node.tls_ok.

Ещё есть отдельный замер скорости: через узел качается небольшой файл и
считается пропускная способность. Результат пишется в node.speed_mbps.

Если бинарника sing-box нет, verify() возвращает пустой список, и вызывающая
сторона откатывается на TCP-проверку.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import ssl
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

# Те же адреса, но по HTTPS. Здесь важна именно проверка сертификата:
# узел, который читает трафик и подменяет сертификаты, её не пройдёт.
TLS_PROBE_URLS = (
    "https://cp.cloudflare.com/generate_204",
    "https://connectivitycheck.gstatic.com/generate_204",
)

# Замер скорости: качаем небольшой файл через узел. Пробуем несколько
# адресов по очереди: часть узлов и сетей не пускает на конкретный хост
# (Cloudflare, например, отвечает 403 на многие серверные адреса).
# Первый удачный замер идёт в результат.
SPEED_TARGETS = (
    "https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/main/output/all-full.txt",
    "https://cdn.jsdelivr.net/gh/sakazxc1400-creator/free-vpn-sub@main/output/all-full.txt",
    "https://proof.ovh.net/files/1Mb.dat",
)
SPEED_BYTES = 200000
SPEED_TIMEOUT = 10.0
# Меньше этого объёма считать нечего: замер получится случайным.
MIN_SPEED_BYTES = 32768

BATCH_SIZE = 150         # узлов на один процесс sing-box
PROBE_TIMEOUT = 8.0      # сек на запрос через узел
PROBE_WORKERS = 75       # параллельных запросов внутри батча
STARTUP_TIMEOUT = 30.0   # сек на подъём sing-box
PORT_BASE = 24000

# Сколько процессов sing-box гонять одновременно. Каждый батч раньше
# ждал своей очереди, из-за чего за отведённый бюджет успевало
# провериться меньше половины кандидатов. Теперь несколько батчей идут
# параллельно: проверка упирается в сеть, а не в CPU, поэтому на 4 ядрах
# раннера три процесса дают почти трёхкратный выигрыш по времени и,
# значит, больше найденных рабочих узлов за тот же бюджет.
VERIFY_PARALLEL = max(1, int(os.environ.get("VERIFY_PARALLEL", "3")))

# Каждый батч получает свой отрезок портов, чтобы параллельные
# процессы sing-box не подрались за один и тот же порт.
PORT_SEGMENT = BATCH_SIZE + 16

# Ниже этого размера батч при падении sing-box не делим: слишком мало
# узлов, чтобы окупить перезапуски.
MIN_BATCH = 20

# Потолок на всю проверку. Кандидатов может быть много тысяч, а прогон
# ограничен временем job'а в CI, поэтому по истечении бюджета
# останавливаемся и отдаём то, что уже нашли.
VERIFY_BUDGET = 25 * 60

# Замер скорости идёт уже после проверки, когда рабочие узлы известны.
# Это дорого: через каждый узел качается файл, поэтому берём только
# лучших по задержке и ограничиваем время.
MAX_SPEED_NODES = 200
SPEED_BUDGET = 8 * 60
SPEED_WORKERS = 30

# Замер скорости берёт свой отрезок портов, чтобы не зависеть от того,
# успели ли освободиться порты фазы проверки.
SPEED_PORT_BASE = 48000


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


def free_ports(count: int, start: int = PORT_BASE) -> list[int]:
    """Подбирает свободные порты, начиная с start."""
    ports: list[int] = []
    port = start
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


def wait_ready(proc, ports: list[int], deadline: float) -> str:
    """
    Ждёт, пока sing-box начнёт слушать порты. Возвращает статус:
      "ready"   — порты поднялись, можно проверять;
      "exited"  — процесс завершился сам (обычно битый конфиг);
      "timeout" — время вышло, процесс ещё жив.
    Ранний выход на "exited" важен: битый конфиг убивает sing-box за
    секунду, и ждать оставшиеся STARTUP_TIMEOUT смысла нет.
    """
    probe = ports[: min(5, len(ports))]
    while time.time() < deadline:
        if proc.poll() is not None:
            return "exited"
        ready = 0
        for port in probe:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    ready += 1
            except OSError:
                break
        if ready == len(probe):
            return "ready"
        time.sleep(0.4)
    return "timeout"


def stop_singbox(proc, error_tail: bool = False) -> str:
    """
    Останавливает процесс sing-box. При error_tail возвращает последние
    строки stderr — там sing-box пишет причину, почему не стартовал.
    """
    err = ""
    proc.terminate()
    try:
        _, stderr = proc.communicate(timeout=5)
        if error_tail and stderr:
            err = " | ".join(stderr.decode("utf-8", "ignore").strip().splitlines()[-2:])
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
    return err


def probe_one(port: int) -> tuple[int | None, bool]:
    """
    Запрос через локальный прокси. Возвращает пару
    (задержка в мс или None, прошёл ли HTTPS с проверкой сертификата).
    """
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({
            "http": f"http://127.0.0.1:{port}",
            "https": f"http://127.0.0.1:{port}",
        }),
        urllib.request.HTTPSHandler(),
    )
    latency: int | None = None
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
                    latency = int((time.perf_counter() - start) * 1000)
                    break
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                ValueError, TimeoutError):
            continue

    if latency is None:
        return None, False
    return latency, probe_tls(port)


def probe_tls(port: int) -> bool:
    """
    HTTPS-запрос через узел с полной проверкой сертификата.

    Узел, который вклинивается в TLS и подменяет сертификаты, предъявит
    свой сертификат, и проверка не пройдёт. Такой узел сможет читать
    трафик пользователя, поэтому в основную подписку он не попадает.
    """
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({
            "http": f"http://127.0.0.1:{port}",
            "https": f"http://127.0.0.1:{port}",
        }),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    for url in TLS_PROBE_URLS:
        try:
            with opener.open(url, timeout=PROBE_TIMEOUT) as resp:
                if resp.status not in (200, 204):
                    continue
                body = resp.read(64)
                if resp.status == 204 and body:
                    continue
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                ValueError, TimeoutError, ssl.SSLError):
            continue
    return False


def probe_speed(port: int, nbytes: int = SPEED_BYTES) -> float | None:
    """
    Качает небольшой файл через узел и считает скорость в Мбит/с.
    None означает, что замер не удался или узел слишком медленный.
    """
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({
            "http": f"http://127.0.0.1:{port}",
            "https": f"http://127.0.0.1:{port}",
        }),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    for url in SPEED_TARGETS:
        start = time.perf_counter()
        try:
            with opener.open(url, timeout=SPEED_TIMEOUT) as resp:
                data = resp.read(nbytes)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                ValueError, TimeoutError, ssl.SSLError):
            continue

        elapsed = time.perf_counter() - start
        if elapsed <= 0 or len(data) < MIN_SPEED_BYTES:
            continue
        return round(len(data) * 8 / elapsed / 1e6, 1)
    return None


def default_probe(port: int, node: object) -> int | None:
    """Обычная проверка узла: доступ в интернет плюс проверка сертификата."""
    latency, tls_ok = probe_one(port)
    if latency is not None:
        node.tls_ok = tls_ok
    return latency


def speed_probe(port: int, node: object) -> float | None:
    """Замер скорости узла."""
    mbps = probe_speed(port)
    if mbps is not None:
        node.speed_mbps = mbps
    return mbps


def prepare_nodes(nodes: list) -> list[tuple[object, dict]]:
    """Собирает outbound-конфиги для узлов. Негодные ссылки пропускает."""
    prepared: list[tuple[object, dict]] = []
    for node in nodes:
        built = outbound.build(node.raw)
        if built is not None:
            prepared.append((node, built))
    return prepared


def verify_batch(nodes: list, singbox: str,
                 port_base: int = PORT_BASE) -> list[tuple[object, int]]:
    """Проверяет один батч узлов. Возвращает пары (узел, задержка_мс).

    port_base — начало отрезка портов для этого батча. Параллельные
    батчи получают разные отрезки и не мешают друг другу.
    """
    prepared = prepare_nodes(nodes)
    if not prepared:
        return []
    return _verify_prepared(prepared, singbox, port_base)


def _verify_prepared(prepared: list[tuple[object, dict]], singbox: str,
                     port_base: int = PORT_BASE, probe=None,
                     workers: int = PROBE_WORKERS) -> list:
    """probe(port, node) -> значение или None. По умолчанию проверка доступа."""
    probe = probe or default_probe
    ports = free_ports(len(prepared), port_base)
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
            status = wait_ready(proc, ports, time.time() + STARTUP_TIMEOUT)
            if status != "ready":
                err = stop_singbox(proc, error_tail=(status == "exited"))
                if status == "exited" and len(prepared) >= MIN_BATCH * 2:
                    # Один битый конфиг валит весь процесс sing-box. Без
                    # деления здесь терялись бы все 150 узлов батча из-за
                    # одной ссылки. Делим пополам и спасаем здоровую часть.
                    log(f"    батч не стартовал ({err or 'без объяснений'}), "
                        f"делю {len(prepared)} узлов пополам")
                    mid = len(prepared) // 2
                    # Второй половине даём порты после первой, чтобы
                    # хвост закрывающегося процесса не столкнулся с ним.
                    return (_verify_prepared(prepared[:mid], singbox, port_base,
                                            probe, workers)
                            + _verify_prepared(prepared[mid:], singbox,
                                               port_base + mid, probe, workers))
                log(f"    батч из {len(prepared)} узлов пропущен: "
                    f"{err or 'sing-box не поднялся'}")
                return []

            results: list[tuple[object, int]] = []
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(probe, ports[i], prepared[i][0]): prepared[i][0]
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
            if proc.poll() is None:
                stop_singbox(proc)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def verify(nodes: list, need: int) -> list[tuple[object, int]]:
    """
    Проверяет узлы батчами, пока не наберётся need рабочих, не кончатся
    кандидаты или не выйдет бюджет времени (VERIFY_BUDGET).
    Возвращает пары (узел, задержка_мс), отсортированные по задержке.

    Батчи идут в несколько потоков (VERIFY_PARALLEL процессов sing-box):
    так за тот же бюджет успевает провериться больше кандидатов, и
    рабочих узлов в итоге больше.
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
    deadline = time.time() + VERIFY_BUDGET

    # Раскладываем кандидатов по батчам и даём каждому свой отрезок портов.
    batches = [
        (index // BATCH_SIZE, nodes[index:index + BATCH_SIZE])
        for index in range(0, len(nodes), BATCH_SIZE)
    ]
    log(f"    параллельно процессов: {VERIFY_PARALLEL}")

    for wave_start in range(0, len(batches), VERIFY_PARALLEL):
        wave = batches[wave_start:wave_start + VERIFY_PARALLEL]
        with ThreadPoolExecutor(max_workers=len(wave)) as pool:
            futures = {
                pool.submit(
                    verify_batch, batch, singbox,
                    PORT_BASE + batch_index * PORT_SEGMENT,
                ): batch
                for batch_index, batch in wave
            }
            for fut in as_completed(futures):
                batch = futures[fut]
                try:
                    good.extend(fut.result())
                except Exception as exc:
                    log(f"    батч из {len(batch)} узлов упал: "
                        f"{type(exc).__name__}")
                checked += len(batch)
        log(f"    проверено {checked}/{len(nodes)}, рабочих {len(good)}")
        if len(good) >= need:
            break
        if time.time() >= deadline:
            log(f"    бюджет времени ({VERIFY_BUDGET}s) исчерпан, останавливаюсь")
            break

    good.sort(key=lambda pair: pair[1])
    return good


def measure_speed(nodes: list, singbox: str | None = None) -> int:
    """
    Замеряет скорость узлов: через каждый качается небольшой файл.
    Результат пишется в node.speed_mbps. Возвращает число удачных замеров.

    Список приходит из сборки: обычно это уже отобранная основная
    подписка, чтобы скорость была видна у каждого её узла. Замер дорогой
    по трафику, поэтому сверху есть потолок MAX_SPEED_NODES и общий
    бюджет времени SPEED_BUDGET.
    """
    singbox = singbox or find_singbox()
    if not singbox:
        log("    sing-box не найден — замер скорости пропущен")
        return 0

    prepared = prepare_nodes(nodes[:MAX_SPEED_NODES])
    if not prepared:
        return 0

    log(f"    замер скорости: {len(prepared)} узлов по "
        f"{SPEED_BYTES // 1024} КБ, параллельно {SPEED_WORKERS}")
    deadline = time.time() + SPEED_BUDGET
    measured = 0
    for index in range(0, len(prepared), SPEED_WORKERS):
        if time.time() >= deadline:
            log(f"    бюджет замера ({SPEED_BUDGET}s) исчерпан")
            break
        chunk = prepared[index:index + SPEED_WORKERS]
        # Отрезок портов отдельный от проверки: так замер не зависит от того,
        # успели ли освободиться порты предыдущей фазы.
        results = _verify_prepared(
            chunk, singbox,
            SPEED_PORT_BASE + (index % 64) * PORT_SEGMENT,
            probe=speed_probe, workers=SPEED_WORKERS,
        )
        measured += len(results)
        log(f"    замерено {min(index + len(chunk), len(prepared))}"
            f"/{len(prepared)}, с результатом {measured}")
    return measured


if __name__ == "__main__":
    path = find_singbox()
    print(f"sing-box: {path or 'не найден'}")
    sys.exit(0 if path else 1)
