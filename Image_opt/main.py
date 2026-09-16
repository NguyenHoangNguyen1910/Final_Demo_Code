from __future__ import annotations

import json
import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from task import celery_app, optimize_image


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/postgres",
)
REDIS_CACHE_URL = os.getenv("REDIS_CACHE_URL", "redis://localhost:6379/0")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = Path(tempfile.gettempdir()) / "best_practice_demo_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    app.state.cache = redis.Redis.from_url(REDIS_CACHE_URL, decode_responses=True)

    async with app.state.db.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                task_id UUID PRIMARY KEY,
                original_filename TEXT NOT NULL,
                input_path TEXT NOT NULL,
                output_path TEXT,
                status TEXT NOT NULL,
                target_width INTEGER NOT NULL,
                quality INTEGER NOT NULL,
                output_format TEXT NOT NULL,
                original_size BIGINT,
                optimized_size BIGINT,
                reduction_percent NUMERIC(7,2),
                original_width INTEGER,
                original_height INTEGER,
                width INTEGER,
                height INTEGER,
                media_type TEXT,
                error TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )

    yield

    await app.state.cache.aclose()
    await app.state.db.close()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    request: Request,
    file: UploadFile = File(...),
    width: int = Form(1280),
    quality: int = Form(80),
    output_format: str = Form("webp"),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image.")

    output_format = output_format.lower()
    if output_format not in {"webp", "jpeg"}:
        raise HTTPException(status_code=400, detail="Format must be webp or jpeg.")

    task_id = uuid.uuid4()
    suffix = Path(file.filename or "upload.jpg").suffix.lower()
    input_path = UPLOAD_DIR / f"{task_id}{suffix}"

    with input_path.open("wb") as f:
        f.write(await file.read())

    await request.app.state.db.execute(
        """
        INSERT INTO jobs (
            task_id, original_filename, input_path, status,
            target_width, quality, output_format, original_size
        )
        VALUES ($1,$2,$3,'PENDING',$4,$5,$6,$7)
        """,
        task_id,
        file.filename or "image",
        str(input_path),
        width,
        quality,
        output_format,
        input_path.stat().st_size,
    )

    optimize_image.apply_async(
        args=[str(task_id), str(input_path), width, quality, output_format],
        task_id=str(task_id),
        queue="image",
    )

    return {"task_id": str(task_id), "status": "PENDING"}


@app.get("/jobs/{task_id}")
async def get_job(task_id: uuid.UUID, request: Request):
    cache_key = f"job:{task_id}"

    cached = await request.app.state.cache.get(cache_key)
    if cached:
        data = json.loads(cached)
        data["cache"] = "HIT"
        return data

    row = await request.app.state.db.fetchrow(
        "SELECT * FROM jobs WHERE task_id = $1",
        task_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="Job not found.")

    data = {
        "task_id": str(row["task_id"]),
        "status": row["status"],
    }

    if row["status"] == "SUCCESS":
        data["result"] = {
            "original_size": row["original_size"],
            "optimized_size": row["optimized_size"],
            "reduction_percent": float(row["reduction_percent"]),
            "original_width": row["original_width"],
            "original_height": row["original_height"],
            "width": row["width"],
            "height": row["height"],
        }
        await request.app.state.cache.set(cache_key, json.dumps(data), ex=60)

    elif row["status"] == "FAILED":
        data["error"] = row["error"]

    data["cache"] = "MISS"
    return data


@app.get("/downloads/{task_id}")
async def download(task_id: uuid.UUID, request: Request):
    row = await request.app.state.db.fetchrow(
        "SELECT status, output_path, media_type FROM jobs WHERE task_id = $1",
        task_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="Job not found.")

    if row["status"] != "SUCCESS":
        raise HTTPException(status_code=409, detail="Job is not finished.")

    output_path = Path(row["output_path"])

    return FileResponse(
        output_path,
        filename=output_path.name,
        media_type=row["media_type"],
    )
