import asyncio
import logging
from contextlib import asynccontextmanager
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError
from fastapi import FastAPI

# Your Kafka bootstrap server
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"

# Create the producer instance
producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)

# payment_service/config.py

DATABASE_URL = "postgresql://postgres:password@order_db:5432/order_db"
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"

logger = logging.getLogger(__name__)


# Helper function: attempts to start the producer with retries.
async def start_producer_with_retry(producer, retries=5, delay=3):
    for attempt in range(1, retries + 1):
        try:
            await producer.start()
            logger.info("Kafka producer started successfully (order_service).")
            return
        except KafkaConnectionError:
            logger.info(f"Order Service: Attempt {attempt}/{retries} - Kafka not ready. Retrying in {delay} seconds...")
            await asyncio.sleep(delay)
    raise KafkaConnectionError("Order Service: Kafka not ready after several retries.")

# Assume order_event_consumer is defined elsewhere in order_service/consumers.py
from order_service.consumers import order_event_consumer

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Use the retry function to start the producer
    logger.info("Starting producer...")
    await start_producer_with_retry(producer)
    logger.info("Producer started successfully.")
    # Start the consumer task
    consumer_task = asyncio.create_task(order_event_consumer())
    yield
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await producer.stop()
