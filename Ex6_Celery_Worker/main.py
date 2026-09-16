import json
import os
import uuid
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel

from task import process_job


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    app.state.cache = redis.from_url(REDIS_CACHE_URL, decode_responses=True)

    async with app.state.db.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs_ex6 (
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


app = FastAPI(title="Ex6 - Redis Broker + Celery Worker", lifespan=lifespan)


@app.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job(data: JobRequest, request: Request):
    job_id = str(uuid.uuid4())

    async with request.app.state.db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO jobs_ex6 (id, input_text, status)
            VALUES ($1, $2, 'PENDING')
            """,
            job_id,
            data.text,
        )

    try:
        # FastAPI chỉ enqueue. Celery worker process riêng mới chạy task.
        process_job.apply_async(args=[job_id, data.text], queue="jobs")
    except Exception as exc:
        async with request.app.state.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs_ex6
                SET status='FAILED', error=$2, updated_at=NOW()
                WHERE id=$1
                """,
                job_id,
                f"enqueue failed: {exc}",
            )
        raise HTTPException(
            status_code=503,
            detail={"message": "Could not enqueue task", "job_id": job_id},
        ) from exc

    return {
        "job_id": job_id,
        "status": "PENDING",
        "status_url": f"/jobs/{job_id}",
    }


@app.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request):
    cache_key = f"job-ex6:{job_id}"

    cached = await request.app.state.cache.get(cache_key)
    if cached is not None:
        data = json.loads(cached)
        data["cache"] = "HIT"
        return data

    async with request.app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM jobs_ex6 WHERE id=$1",
            job_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    data = row_to_dict(row)

    if data["status"] in TERMINAL_STATUSES:
        await request.app.state.cache.set(
            cache_key,
            json.dumps(data),
            ex=CACHE_TTL_SECONDS,
        )

    data["cache"] = "MISS"
    return data
