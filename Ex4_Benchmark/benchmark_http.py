import asyncio
import math
import os
import statistics
import time

import httpx


REQUESTS = int(os.getenv("BENCH_REQUESTS", "1000"))
CONCURRENCY_LEVELS = [
    int(value.strip())
    for value in os.getenv("BENCH_CONCURRENCY", "10,50,100").split(",")
    if value.strip()
]
WARMUP_REQUESTS = int(os.getenv("BENCH_WARMUP", "50"))
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percent * len(ordered)) - 1)
    return ordered[index]


async def send_request(client: httpx.AsyncClient, method: str, path: str, i: int):
    if method == "GET":
        return await client.get(path)
    return await client.post(path, json={"value": f"http-{i}"})


async def benchmark(name: str, method: str, path: str, concurrency: int):
    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency,
    )

    async with httpx.AsyncClient(
        base_url=BASE_URL,
        limits=limits,
        timeout=30.0,
        trust_env=False,
    ) as client:
        # Warm-up để giảm ảnh hưởng của connection setup/cold start.
        for i in range(WARMUP_REQUESTS):
            await send_request(client, method, path, i)

        semaphore = asyncio.Semaphore(concurrency)
        latencies: list[float] = []
        success = 0
        errors = 0

        async def one_request(i: int):
            nonlocal success, errors

            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await send_request(client, method, path, i)
                    if response.is_success:
                        success += 1
                    else:
                        errors += 1
                except httpx.HTTPError:
                    errors += 1
                finally:
                    latencies.append(time.perf_counter() - started)

        started = time.perf_counter()
        await asyncio.gather(*(one_request(i) for i in range(REQUESTS)))
        total = time.perf_counter() - started

    completed_rps = REQUESTS / total if total else 0.0
    success_rps = success / total if total else 0.0
    error_rate = (errors / REQUESTS * 100) if REQUESTS else 0.0

    print(f"\n=== {name} | concurrency={concurrency} ===")
    print(f"Requests      : {REQUESTS}")
    print(f"Success       : {success}")
    print(f"Errors        : {errors}")
    print(f"Error rate    : {error_rate:.2f} %")
    print(f"Total time    : {total:.3f} s")
    print(f"Completed RPS : {completed_rps:.2f} req/s")
    print(f"Success RPS   : {success_rps:.2f} req/s")
    print(f"Average       : {statistics.mean(latencies) * 1000:.2f} ms")
    print(f"P50           : {percentile(latencies, 0.50) * 1000:.2f} ms")
    print(f"P95           : {percentile(latencies, 0.95) * 1000:.2f} ms")
    print(f"P99           : {percentile(latencies, 0.99) * 1000:.2f} ms")


async def main():
    tests = [
        ("HTTP baseline /ping", "GET", "/ping"),
        ("HTTP + PostgreSQL SELECT", "GET", "/db-read"),
        ("HTTP + PostgreSQL INSERT", "POST", "/db-write"),
    ]

    for concurrency in CONCURRENCY_LEVELS:
        for name, method, path in tests:
            await benchmark(name, method, path, concurrency)


if __name__ == "__main__":
    asyncio.run(main())
