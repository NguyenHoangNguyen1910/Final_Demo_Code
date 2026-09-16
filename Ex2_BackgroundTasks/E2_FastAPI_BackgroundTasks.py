import asyncio

from fastapi import BackgroundTasks, FastAPI, status
from pydantic import BaseModel


app = FastAPI(title="Ex2 - FastAPI BackgroundTasks")


class InferRequest(BaseModel):
    text: str


async def process_task(text: str) -> None:
    # Đây chỉ là background function, KHÔNG phải worker service độc lập.
    print(f"Background task started: {text}")

    await asyncio.sleep(5)
    result = text.upper()

    print(f"Background task finished: {result}")


@app.get("/health")
async def health():
    return {"status": "alive"}


@app.post("/infer", status_code=status.HTTP_202_ACCEPTED)
async def infer(data: InferRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_task, data.text)

    return {
        "status": "ACCEPTED",
        "message": "Response returned without waiting for task completion",
    }
