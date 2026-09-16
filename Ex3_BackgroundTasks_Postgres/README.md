# Ex3 - BackgroundTasks + PostgreSQL

Ex2 trả `202`, nhưng client cần biết job đang ở đâu.

```text
POST /jobs
FastAPI -> PostgreSQL: PENDING
        -> BackgroundTasks
        -> 202 + job_id

process_job()
PENDING -> PROCESSING -> SUCCESS / FAILED
                      -> PostgreSQL

GET /jobs/{job_id}
FastAPI -> PostgreSQL -> status/result
```

PostgreSQL lưu durable state; PostgreSQL không chạy task.

## Chạy

```bash
uv run --with fastapi --with uvicorn --with asyncpg \
  uvicorn E3_FastAPI_BackgroundTasks_Postgres:app --reload
```

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"text":"hello postgres"}'
```

```bash
curl http://127.0.0.1:8000/jobs/<JOB_ID>
```
## Kết quả : 

```database
{"id":"a32f0d66-dead-4cf8-9980-fbd24130981f","input_text":"hello postgres","status":"SUCCESS","result":"HELLO POSTGRES","error":null,"created_at":"2026-09-16T16:33:07.608326+00:00","updated_at":"2026-09-16T16:33:12.620122+00:00"}
```
