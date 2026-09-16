import asyncio
import os
import uuid
from contextlib import asynccontextmanager

import asyncpg
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, status
from pydantic import BaseModel


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/postgres",
)


class JobRequest(BaseModel):
    text: str


def row_to_dict(row: asyncpg.Record) -> dict:
    data = dict(row)
    for key in ("created_at", "updated_at"):
        if data.get(key) is not None:
            data[key] = data[key].isoformat()
    return data


async def process_job(pool: asyncpg.Pool, job_id: str, text: str) -> None:
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs_ex3
                SET status='PROCESSING', error=NULL, updated_at=NOW()
                WHERE id=$1
                """,
                job_id,
            )

        print(f"Background task started: {job_id}")

        await asyncio.sleep(5)
        result = text.upper()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs_ex3
                SET status='SUCCESS', result=$2, error=NULL, updated_at=NOW()
                WHERE id=$1
                """,
                job_id,
                result,
            )

        print(f"Background task finished: {job_id} -> {result}")

    except Exception as exc:
        # Demo đơn giản: cố gắng ghi FAILED để job không bị kẹt PROCESSING.
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE jobs_ex3
                    SET status='FAILED', error=$2, updated_at=NOW()
                    WHERE id=$1
                    """,
                    job_id,
                    str(exc),
                )
        finally:
            print(f"Background task failed: {job_id}: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10,
    )

    async with app.state.db.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs_ex3 (
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

    yield
    await app.state.db.close()


app = FastAPI(title="Ex3 - BackgroundTasks + PostgreSQL", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "alive"}


@app.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    data: JobRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    job_id = str(uuid.uuid4())
    pool = request.app.state.db

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO jobs_ex3 (id, input_text, status)
            VALUES ($1, $2, 'PENDING')
            """,
            job_id,
            data.text,
        )

    background_tasks.add_task(process_job, pool, job_id, data.text)

    return {
        "job_id": job_id,
        "status": "PENDING",
        "status_url": f"/jobs/{job_id}",
    }


@app.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request):
    async with request.app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM jobs_ex3 WHERE id=$1",
            job_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return row_to_dict(row)
