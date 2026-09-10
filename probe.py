import asyncio
import time
import aiohttp
from aiohttp_socks import ProxyConnector


async def check_proxy_latency(proxy_socks5_url: str, test_url: str = "http://cp.cloudflare.com/generate_204", timeout_sec: float = 3.5) -> tuple[bool, int]:
    """
    Выполняет реальный HTTP-запрос через локальный SOCKS-порт прокси.
    Возвращает (доступность, rtt_в_миллисекундах).
    """
    start = time.perf_counter()
    try:
        connector = ProxyConnector.from_url(proxy_socks5_url)
        timeout = aiohttp.ClientTimeout(total=timeout_sec)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(test_url, timeout=timeout) as resp:
                latency = int((time.perf_counter() - start) * 1000)
                is_alive = (resp.status == 204 or resp.status == 200)
                return (is_alive, latency)
    except Exception:
        return (False, 0)


async def filter_and_sort_nodes(tested_results: list[dict], max_ping_ms: int = 1800) -> list[str]:
    """
    Фильтрует рабочие ноды и сортирует их по минимальной задержке.
    """
    alive = [
        item for item in tested_results
        if item.get("alive") and 0 < item.get("rtt", 0) <= max_ping_ms
    ]
    alive.sort(key=lambda x: x["rtt"])
    return [item["link"] for item in alive]


if __name__ == "__main__":
    async def sample_test():
        print("Проверка подключения через SOCKS5 127.0.0.1:10808...")
        alive, rtt = await check_proxy_latency("socks5://127.0.0.1:10808")
        if alive:
            print(f"Нода активна, пинг: {rtt} ms")
        else:
            print("Нода недоступна")

    asyncio.run(sample_test())
