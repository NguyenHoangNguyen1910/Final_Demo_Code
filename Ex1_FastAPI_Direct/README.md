# Ex1 - FastAPI xử lý trực tiếp

```text
Client -> FastAPI -> process_task() 5s -> Response
```

Request phải chờ task hoàn thành.

## Chạy

```bash
uv run --with fastapi --with uvicorn \
  uvicorn E1_FastAPI_Direct:app --reload
```

```bash
curl -X POST http://127.0.0.1:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"text":"hello fastapi"}'
```

## Kết quả : 

```backend
FastAPI started: hello fastapi
FastAPI finished: HELLO FASTAPI
```

```frontend
{"status":"COMPLETED","result":"HELLO FASTAPI"}
```
