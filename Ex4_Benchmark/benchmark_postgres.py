import asyncio
import math
import os
import statistics
import time

import asyncpg


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/postgres",
)
OPERATIONS = int(os.getenv("DB_BENCH_OPERATIONS", "1000"))
CONCURRENCY = int(os.getenv("DB_BENCH_CONCURRENCY", "50"))
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
WARMUP_OPERATIONS = int(os.getenv("DB_BENCH_WARMUP", "50"))


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percent * len(ordered)) - 1)
    return ordered[index]


async def prepare(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS benchmark_items (
                id BIGSERIAL PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

        count = await conn.fetchval("SELECT COUNT(*) FROM benchmark_items")
        if count == 0:
            await conn.executemany(
                "INSERT INTO benchmark_items (value) VALUES ($1)",
                [(f"seed-{i}",) for i in range(1, 101)],
            )


async def execute_operation(pool: asyncpg.Pool, operation: str, i: int) -> None:
    async with pool.acquire() as conn:
        if operation == "read":
            await conn.fetchrow(
                "SELECT id, value FROM benchmark_items ORDER BY id LIMIT 1"
            )
        else:
            await conn.execute(
                "INSERT INTO benchmark_items (value) VALUES ($1)",
                f"direct-{i}",
            )


async def run_benchmark(pool: asyncpg.Pool, name: str, operation: str):
    for i in range(WARMUP_OPERATIONS):
        await execute_operation(pool, operation, i)

    semaphore = asyncio.Semaphore(CONCURRENCY)
    latencies: list[float] = []
    errors = 0

    async def one_operation(i: int):
        nonlocal errors
        async with semaphore:
            started = time.perf_counter()
            try:
                await execute_operation(pool, operation, i)
            except Exception:
                errors += 1
            finally:
                latencies.append(time.perf_counter() - started)

    started = time.perf_counter()
    await asyncio.gather(*(one_operation(i) for i in range(OPERATIONS)))
    total = time.perf_counter() - started

    successful = OPERATIONS - errors
    print(f"\n=== {name} ===")
    print(f"Operations    : {OPERATIONS}")
    print(f"Concurrency   : {CONCURRENCY}")
    print(f"DB pool size  : {POOL_SIZE}")
    print(f"Success       : {successful}")
    print(f"Errors        : {errors}")
    print(f"Total time    : {total:.3f} s")
    print(f"Completed OPS : {OPERATIONS / total:.2f} ops/s")
    print(f"Success OPS   : {successful / total:.2f} ops/s")
    print(f"Average       : {statistics.mean(latencies) * 1000:.2f} ms")
    print(f"P50           : {percentile(latencies, 0.50) * 1000:.2f} ms")
    print(f"P95           : {percentile(latencies, 0.95) * 1000:.2f} ms")
    print(f"P99           : {percentile(latencies, 0.99) * 1000:.2f} ms")


async def main():
    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=POOL_SIZE,
    )

    try:
        await prepare(pool)
        await run_benchmark(pool, "PostgreSQL direct SELECT", "read")
        await run_benchmark(pool, "PostgreSQL direct INSERT", "write")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
