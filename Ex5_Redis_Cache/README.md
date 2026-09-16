# Ex5 - PostgreSQL + Redis Cache

Chỉ thêm cache khi benchmark/traffic thực tế cho thấy repeated reads là bottleneck phù hợp.

```text
GET /jobs/{id}
FastAPI -> Redis Cache
           | HIT  -> Response
           | MISS
           v
        PostgreSQL
           |
           +-> cache terminal result -> Response
```

Demo này chỉ cache `SUCCESS/FAILED`, không cache `PENDING/PROCESSING`, để polling trạng thái đang thay đổi không bị stale lâu.

## Chạy

Terminal 1:

```bash
redis-server
```

Terminal 2:

```bash
export DATABASE_URL='postgresql://postgres:123456@127.0.0.1:5432/postgres'
uv run --with fastapi --with uvicorn --with asyncpg --with redis \
  uvicorn E5_FastAPI_Postgres_Redis_Cache:app --reload
```

Tạo job:

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"text":"hello cache"}'
```

Poll đến `SUCCESS`, sau đó GET lại cùng URL:

```bash
curl http://127.0.0.1:8000/jobs/<JOB_ID>
```
## Kết quả : 
```MISS
{"id":"0c429e36-a742-4743-82aa-891a15f50021","input_text":"hello cache","status":"SUCCESS","result":"HELLO CACHE","error":null,"created_at":"2026-09-16T16:38:19.712587+00:00","updated_at":"2026-09-16T16:38:24.722406+00:00","cache":"MISS"}
```

```HIT
{"id":"0c429e36-a742-4743-82aa-891a15f50021","input_text":"hello cache","status":"SUCCESS","result":"HELLO CACHE","error":null,"created_at":"2026-09-16T16:38:19.712587+00:00","updated_at":"2026-09-16T16:38:24.722406+00:00","cache":"HIT"}
```

Redis ở bài này là **Cache**, chưa phải Broker.
