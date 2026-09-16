import asyncio

from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI(title="Ex1 - FastAPI Direct Task")


class InferRequest(BaseModel):
    text: str


async def process_task(text: str) -> str:
    # Giả lập công việc mất 5 giây.
    # asyncio.sleep mô phỏng waiting/I/O; request vẫn phải chờ response.
    await asyncio.sleep(5)
    return text.upper()


@app.get("/health")
async def health():
    return {"status": "alive"}


@app.post("/infer")
async def infer(data: InferRequest):
    print(f"FastAPI started: {data.text}")

    result = await process_task(data.text)

    print(f"FastAPI finished: {result}")
    return {
        "status": "COMPLETED",
        "result": result,
    }
