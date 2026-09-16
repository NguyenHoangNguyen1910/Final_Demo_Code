import os
import time

from celery import Celery


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/postgres",
)
REDIS_CACHE_URL = os.getenv("REDIS_CACHE_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")


celery_app = Celery("ex6_tasks", broker=CELERY_BROKER_URL)
celery_app.conf.update(
    task_ignore_result=True,
    task_default_queue="jobs",
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="process_job")
def process_job(job_id: str, text: str) -> None:
    import psycopg
    import redis

    cache = redis.Redis.from_url(REDIS_CACHE_URL, decode_responses=True)
    cache_key = f"job-ex6:{job_id}"

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs_ex6
                    SET status='PROCESSING', error=NULL, updated_at=NOW()
                    WHERE id=%s
                    """,
                    (job_id,),
                )
            conn.commit()

        cache.delete(cache_key)
        print(f"Celery worker started: {job_id}")

        time.sleep(5)
        result = text.upper()

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs_ex6
                    SET status='SUCCESS', result=%s, error=NULL, updated_at=NOW()
                    WHERE id=%s
                    """,
                    (result, job_id),
                )
            conn.commit()

        cache.delete(cache_key)
        print(f"Celery worker finished: {job_id} -> {result}")

    except Exception as exc:
        # Cố gắng persist FAILED. Nếu DB cũng hỏng, Celery log vẫn giữ exception.
        try:
            with psycopg.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE jobs_ex6
                        SET status='FAILED', error=%s, updated_at=NOW()
                        WHERE id=%s
                        """,
                        (str(exc), job_id),
                    )
                conn.commit()
        finally:
            cache.delete(cache_key)
            raise
