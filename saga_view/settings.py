import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
DATABASE_URL = "postgresql://postgres:password@saga_db:5432/saga_db"

@asynccontextmanager
async def lifespan(app: FastAPI):
    from saga_view.consumers import process_saga_events
    consumer_task = asyncio.create_task(process_saga_events())
    yield
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
