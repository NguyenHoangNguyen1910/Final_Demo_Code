# Best Practice Demo

## Structure

```text
Best_Practice_Demo/
├── static/
│   └── index.html
├── main.py
├── task.py
├── requirements.txt
└── README.md
```

## Flow

```text
Browser
  ↓
FastAPI
  ├── PostgreSQL
  └── Redis Broker
         ↓
      Celery Worker
         ↓
       Pillow
         ↓
    PostgreSQL

GET /jobs/{id}
FastAPI → Redis Cache → PostgreSQL
```

## Run

Redis:

```bash
redis-server
```

Worker:

```bash
uv run --with-requirements requirements.txt \
  celery -A task:celery_app worker -Q image --loglevel=INFO --concurrency=1
```

FastAPI:

```bash
uv run --with-requirements requirements.txt \
  uvicorn main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```
