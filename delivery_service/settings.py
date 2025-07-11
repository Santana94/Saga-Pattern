import asyncio
import logging
from contextlib import asynccontextmanager
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError
from fastapi import FastAPI

KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)

DATABASE_URL = "postgresql://postgres:password@delivery_db:5432/delivery_db"
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"

logger = logging.getLogger(__name__)

async def start_producer_with_retry(producer, retries=5, delay=3):
    for attempt in range(1, retries + 1):
        try:
            await producer.start()
            logger.info("Kafka producer started successfully (delivery_service).")
            return
        except KafkaConnectionError:
            logger.info(f"Delivery Service: Attempt {attempt}/{retries} - Kafka not ready. Retrying in {delay} seconds...")
            await asyncio.sleep(delay)
    raise KafkaConnectionError("Delivery Service: Kafka not ready after several retries.")

from delivery_service.consumers import process_payments_for_delivery

@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_producer_with_retry(producer)
    consumer_task = asyncio.create_task(process_payments_for_delivery())
    yield
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await producer.stop()
