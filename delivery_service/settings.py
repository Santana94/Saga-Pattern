import asyncio
import logging
import os
from contextlib import asynccontextmanager
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError
from fastapi import FastAPI

# Use environment variables for configuration
KAFKA_HOST = os.getenv("KAFKA_HOST", "localhost")
KAFKA_PORT = os.getenv("KAFKA_PORT", "9092")
DB_HOST = os.getenv("DB_HOST", "localhost")

KAFKA_BOOTSTRAP_SERVERS = f"{KAFKA_HOST}:{KAFKA_PORT}"
DATABASE_URL = f"postgresql://postgres:password@{DB_HOST}:15434/delivery_db"

producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check if running in development mode (no Kafka)
    if os.getenv("SKIP_KAFKA", "false").lower() == "true":
        logger.info("Skipping Kafka setup for local development")
        yield
        return
    
    await start_producer_with_retry(producer)
    
    # Import consumers here to avoid circular imports
    from delivery_service.consumers import process_payments_for_delivery, process_delivery_compensations
    
    consumer_task = asyncio.create_task(process_payments_for_delivery())
    compensation_task = asyncio.create_task(process_delivery_compensations())
    yield
    consumer_task.cancel()
    compensation_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    try:
        await compensation_task
    except asyncio.CancelledError:
        pass
    await producer.stop()
