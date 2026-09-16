# Ex2 - FastAPI + BackgroundTasks

```text
Client -> FastAPI -> add_task() -> 202 Accepted
                         |
                         v
                  process_task()
```

`process_task()` là function chạy nền của FastAPI/Starlette, **không phải Celery worker** và chưa có broker.

## Chạy

```bash
uv run --with fastapi --with uvicorn \
  uvicorn E2_FastAPI_BackgroundTasks:app --reload
```

```bash
curl -X POST http://127.0.0.1:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"text":"hello background"}'
```

## Kết quả : 
```frontend
{"status":"ACCEPTED","message":"Response returned without waiting for task completion"}
```

```backend
Background task started: hello background
Background task finished: HELLO BACKGROUND
```
