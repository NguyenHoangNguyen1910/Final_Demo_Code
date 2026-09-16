# Ex4 - Benchmark HTTP path và PostgreSQL path

Mục tiêu: **định vị bottleneck**, không phải tạo một con số req/s đẹp.

## 1. Chạy API

Khi benchmark, không dùng `--reload`:

```bash
uv run --with fastapi --with uvicorn --with asyncpg \
  uvicorn main:app --host 127.0.0.1 --port 8000
```

## 2. HTTP benchmark

```bash
uv run --with httpx python benchmark_http.py
```

Mặc định đo concurrency `10, 50, 100` cho:

```text
/ping       HTTP baseline
/db-read    HTTP + PostgreSQL SELECT
/db-write   HTTP + PostgreSQL INSERT
```

Có thể đổi:

```bash
BENCH_REQUESTS=2000 BENCH_CONCURRENCY=10,50,100 uv run --with httpx python benchmark_http.py
```

## 3. PostgreSQL direct benchmark

```bash
uv run --with asyncpg python benchmark_postgres.py
```

Nó bỏ FastAPI/Uvicorn khỏi path và đo trực tiếp PostgreSQL qua asyncpg pool.

## Đọc kết quả

```text
HTTP baseline tốt
Direct PostgreSQL tốt
HTTP + DB kém
=> kiểm tra application code / pool / DB round trips / serialization / network
```

```text
Direct PostgreSQL cũng kém
=> kiểm tra query / index / lock / disk / DB resources
```

Redis Cache chỉ hợp lý nếu vấn đề thực tế là **repeated reads phù hợp để cache**.
