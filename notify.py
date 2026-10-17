#!/usr/bin/env python3
"""
Уведомления в Telegram о результате сборки.

Пока не заданы переменные окружения TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID,
ничего никуда не отправляется: функции просто возвращают False. Так модуль
можно спокойно вызывать из сборки, где секреты не настроены.

Проверка вручную:
    TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python3 notify.py "привет"
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

TIMEOUT = 20
SITE = "https://sakazxc1400-creator.github.io/free-vpn-sub/"
ACTIONS = "https://github.com/sakazxc1400-creator/free-vpn-sub/actions"


def config() -> tuple[str, str] | None:
    """Токен и чат из окружения. None, если уведомления не настроены."""
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat:
        return None
    return token, chat


def send(text: str) -> bool:
    """Отправляет сообщение. False, если не настроено или не получилось."""
    settings = config()
    if settings is None:
        return False
    token, chat = settings

    body = json.dumps({
        "chat_id": chat,
        "text": text,
        "disable_web_page_preview": True,
    }).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return False


def summary(report: dict) -> str:
    """Короткая сводка по прогону для сообщения."""
    lines = [
        f"Подписка обновлена: {report.get('updated', '?')}",
        f"Основная: {report.get('published')} узлов, "
        f"полная: {report.get('published_full')}, "
        f"стабильная: {report.get('stable')}",
        f"Стран: {report.get('countries')}, "
        f"адресов: {report.get('servers')}, "
        f"сертификаты проверили у {report.get('tls_ok')}",
    ]

    if report.get("best_latency_ms") is not None:
        lines.append(f"Задержка: лучшая {report['best_latency_ms']} ms, "
                     f"медиана {report['median_latency_ms']} ms")
    if report.get("best_speed_mbps") is not None:
        lines.append(f"Скорость: лучшая {report['best_speed_mbps']} Мбит/с, "
                     f"медиана {report['median_speed_mbps']} Мбит/с")
    lines.append(f"Источников: {report.get('sources_ok')} "
                 f"из {report.get('sources_total')}")
    lines.append(SITE)
    return "\n".join(lines)


def send_report(report: dict) -> bool:
    """Уведомление об удачном прогоне."""
    return send(summary(report))


def send_failure(reason: str) -> bool:
    """Уведомление о неудаче: подписка не обновилась."""
    return send(f"Сборка подписки не прошла.\n{reason}\n{ACTIONS}")


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or "Проверка связи от free-vpn-sub"
    if config() is None:
        print("Уведомления не настроены: нет TELEGRAM_BOT_TOKEN или "
              "TELEGRAM_CHAT_ID.")
        sys.exit(2)
    print("Отправлено." if send(text) else "Не отправилось.")
