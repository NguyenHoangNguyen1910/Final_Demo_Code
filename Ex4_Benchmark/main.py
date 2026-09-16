import os
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request, status
from pydantic import BaseModel


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/postgres",
)
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))


class WriteRequest(BaseModel):
    value: str = "benchmark"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=DB_POOL_SIZE,
    )

    async with app.state.db.acquire() as conn:
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

    yield
    await app.state.db.close()


app = FastAPI(title="Ex4 - HTTP and PostgreSQL Benchmark", lifespan=lifespan)


@app.get("/ping")
async def ping():
    return {"status": "ok"}


@app.get("/db-read")
async def db_read(request: Request):
    async with request.app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, value FROM benchmark_items ORDER BY id LIMIT 1"
        )

    return dict(row)


@app.post("/db-write", status_code=status.HTTP_201_CREATED)
async def db_write(data: WriteRequest, request: Request):
    async with request.app.state.db.acquire() as conn:
        item_id = await conn.fetchval(
            "INSERT INTO benchmark_items (value) VALUES ($1) RETURNING id",
            data.value,
        )

    return {"id": item_id}
