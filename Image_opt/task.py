from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import psycopg
import redis
from celery import Celery
from PIL import Image, ImageOps


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/postgres",
)
REDIS_CACHE_URL = os.getenv("REDIS_CACHE_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")

OUTPUT_DIR = Path(tempfile.gettempdir()) / "best_practice_demo_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

celery_app = Celery("best_practice_demo", broker=CELERY_BROKER_URL)
celery_app.conf.update(
    task_ignore_result=True,
    task_default_queue="image",
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="optimize_image")
def optimize_image(
    task_id: str,
    input_path: str,
    target_width: int,
    quality: int,
    output_format: str,
):
    job_id = uuid.UUID(task_id)
    cache = redis.Redis.from_url(REDIS_CACHE_URL, decode_responses=True)
    cache_key = f"job:{task_id}"

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status='PROCESSING', updated_at=NOW()
                WHERE task_id=%s
                """,
                (job_id,),
            )

        source = Path(input_path)

        with Image.open(source) as img:
            img = ImageOps.exif_transpose(img)
            original_width, original_height = img.size

            if original_width > target_width:
                new_height = round(original_height * target_width / original_width)
                img = img.resize(
                    (target_width, new_height),
                    Image.Resampling.LANCZOS,
                )

            if output_format == "jpeg":
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                output_path = OUTPUT_DIR / f"{task_id}.jpg"
                img.save(output_path, "JPEG", quality=quality, optimize=True)
                media_type = "image/jpeg"
            else:
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                output_path = OUTPUT_DIR / f"{task_id}.webp"
                img.save(output_path, "WEBP", quality=quality, method=6)
                media_type = "image/webp"

            width, height = img.size

        original_size = source.stat().st_size
        optimized_size = output_path.stat().st_size
        reduction = round((1 - optimized_size / original_size) * 100, 2)

        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status='SUCCESS',
                    output_path=%s,
                    optimized_size=%s,
                    reduction_percent=%s,
                    original_width=%s,
                    original_height=%s,
                    width=%s,
                    height=%s,
                    media_type=%s,
                    updated_at=NOW()
                WHERE task_id=%s
                """,
                (
                    str(output_path),
                    optimized_size,
                    reduction,
                    original_width,
                    original_height,
                    width,
                    height,
                    media_type,
                    job_id,
                ),
            )

        cache.delete(cache_key)

    except Exception as exc:
        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status='FAILED', error=%s, updated_at=NOW()
                WHERE task_id=%s
                """,
                (str(exc), job_id),
            )

        cache.delete(cache_key)
        raise

    finally:
        cache.close()
