# Ex6 - Redis Broker + Celery Worker

BackgroundTasks vẫn thuộc web application. Khi cần queue riêng, worker process riêng và scale độc lập:

```text
POST /jobs
FastAPI -> PostgreSQL: PENDING
        -> Redis Broker (/1)
              |
              v
         Celery Worker
              |
              +-> workload
              +-> PostgreSQL: PROCESSING/SUCCESS/FAILED

GET /jobs/{id}
FastAPI -> Redis Cache (/0) -> PostgreSQL on MISS
```

**Redis Cache `/0` và Redis Broker `/1` là hai trách nhiệm khác nhau.**

Bài này không dùng Celery result backend vì PostgreSQL đã lưu business state/result.

## Chạy

Terminal 1:

```bash
redis-server
```

Terminal 2:

```bash
uv run --with "celery[redis]" --with "psycopg[binary]" \
  celery -A task:celery_app worker -Q jobs --loglevel=INFO --concurrency=1
```

Terminal 3:

```bash
uv run --with fastapi --with uvicorn --with asyncpg --with redis --with "celery[redis]" \
  uvicorn main:app --reload
```

Tạo job:

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"text":"hello celery"}'
```

```bash
curl http://127.0.0.1:8000/jobs/<JOB_ID>
```

## Scale worker

Tăng execution slots trên máy hiện tại:

```bash
celery -A task:celery_app worker -Q jobs --concurrency=4
```

Hoặc chạy thêm worker process/máy khác cùng kết nối tới broker.
