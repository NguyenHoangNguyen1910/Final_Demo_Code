import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as redis
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, status
from pydantic import BaseModel


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/postgres",
)
REDIS_CACHE_URL = os.getenv("REDIS_CACHE_URL", "redis://localhost:6379/0")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "60"))
TERMINAL_STATUSES = {"SUCCESS", "FAILED"}


class JobRequest(BaseModel):
    text: str


def row_to_dict(row: asyncpg.Record) -> dict:
    data = dict(row)
    for key in ("created_at", "updated_at"):
        if data.get(key) is not None:
            data[key] = data[key].isoformat()
    return data


async def process_job(
    pool: asyncpg.Pool,
    cache: redis.Redis,
    job_id: str,
    text: str,
) -> None:
    cache_key = f"job-ex5:{job_id}"

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs_ex5
                SET status='PROCESSING', error=NULL, updated_at=NOW()
                WHERE id=$1
                """,
                job_id,
            )

        await cache.delete(cache_key)
        await asyncio.sleep(5)
        result = text.upper()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs_ex5
                SET status='SUCCESS', result=$2, error=NULL, updated_at=NOW()
                WHERE id=$1
                """,
                job_id,
                result,
            )

        await cache.delete(cache_key)

    except Exception as exc:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs_ex5
                SET status='FAILED', error=$2, updated_at=NOW()
                WHERE id=$1
                """,
                job_id,
                str(exc),
            )
        await cache.delete(cache_key)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    app.state.cache = redis.from_url(REDIS_CACHE_URL, decode_responses=True)

    async with app.state.db.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs_ex5 (
                id TEXT PRIMARY KEY,
                input_text TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

    await app.state.cache.ping()
    yield

    await app.state.cache.aclose()
    await app.state.db.close()


app = FastAPI(title="Ex5 - PostgreSQL + Redis Cache", lifespan=lifespan)


@app.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    data: JobRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    job_id = str(uuid.uuid4())

    async with request.app.state.db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO jobs_ex5 (id, input_text, status)
            VALUES ($1, $2, 'PENDING')
            """,
            job_id,
            data.text,
        )

    background_tasks.add_task(
        process_job,
        request.app.state.db,
        request.app.state.cache,
        job_id,
        data.text,
    )

    return {
        "job_id": job_id,
        "status": "PENDING",
        "status_url": f"/jobs/{job_id}",
    }


@app.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request):
    cache_key = f"job-ex5:{job_id}"
    cache = request.app.state.cache

    cached = await cache.get(cache_key)
    if cached is not None:
        data = json.loads(cached)
        data["cache"] = "HIT"
        return data

    async with request.app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM jobs_ex5 WHERE id=$1",
            job_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    data = row_to_dict(row)

    # Không cache PENDING/PROCESSING để polling không bị stale quá lâu.
    # Chỉ cache terminal state, nơi repeated reads thường an toàn hơn.
    if data["status"] in TERMINAL_STATUSES:
        await cache.set(
            cache_key,
            json.dumps(data),
            ex=CACHE_TTL_SECONDS,
        )

    data["cache"] = "MISS"
    return data
