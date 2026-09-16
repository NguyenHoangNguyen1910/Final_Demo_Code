# FastAPI Backend Evolution v2

## README theo từng phần

- [Ex1 - FastAPI xử lý trực tiếp](./Ex1_FastAPI_Direct/README.md)
- [Ex2 - FastAPI + BackgroundTasks](./Ex2_BackgroundTasks/README.md)
- [Ex3 - BackgroundTasks + PostgreSQL](./Ex3_BackgroundTasks_Postgres/README.md)
- [Ex4 - Benchmark](./Ex4_Benchmark/README.md)
- [Ex5 - PostgreSQL + Redis Cache](./Ex5_Redis_Cache/README.md)
- [Ex6 - Redis Broker + Celery Worker](./Ex6_Celery_Worker/README.md)
- [Best Practice Demo - Image Optimizer](./Image_opt/README.md)


Bộ demo này đi theo đúng mạch kiến trúc của presentation:

```text
Ex1  FastAPI xử lý trực tiếp
  ↓ request phải chờ
Ex2  FastAPI + BackgroundTasks
  ↓ cần lưu trạng thái job
Ex3  + PostgreSQL
  ↓ chưa biết bottleneck nằm đâu
Ex4  HTTP benchmark + PostgreSQL direct benchmark
  ↓ nếu repeated read là bottleneck phù hợp để cache
Ex5  + Redis Cache
  ↓ background workload phức tạp, cần tách khỏi web app
Ex6  + Redis Broker + Celery Worker
  ↓
Best Practice Demo: Image Optimizer tổng hợp
```

## Vai trò

- **FastAPI**: HTTP/API layer.
- **BackgroundTasks**: chạy function sau response nhưng vẫn thuộc FastAPI application; không phải worker service độc lập.
- **PostgreSQL**: durable source of truth cho trạng thái/kết quả business.
- **Redis Cache**: giảm repeated reads phù hợp; không thay PostgreSQL.
- **Redis Broker**: vận chuyển task message từ FastAPI tới Celery worker.
- **Celery Worker**: process riêng thực thi workload; có thể scale độc lập.

## Redis trong bộ demo

```text
redis://localhost:6379/0   Redis Cache
redis://localhost:6379/1   Celery Broker
```

Ex6 và Best Practice **không dùng Celery result backend** vì trạng thái/kết quả business đã nằm trong PostgreSQL.

## PostgreSQL

Mặc định:

```text
postgresql://postgres:postgres@localhost:5432/postgres
```

Nếu khác:

```bash
export DATABASE_URL='postgresql://USER:PASSWORD@localhost:5432/DATABASE'
```

## Redis

```bash
redis-server
```

## Lưu ý

Đây là bộ code học kiến trúc. Mỗi bài cố tình nhỏ để nhìn rõ trách nhiệm của từng component. Bài cuối thực tế hơn nhưng vẫn không thay thế đầy đủ các yêu cầu production như auth, object storage, observability, migrations, secrets management và deployment.
