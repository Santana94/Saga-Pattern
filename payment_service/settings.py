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
DATABASE_URL = f"postgresql://postgres:password@{DB_HOST}:15433/payment_db"

producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)

logger = logging.getLogger(__name__)

async def start_producer_with_retry(producer, retries=5, delay=3):
    for attempt in range(1, retries + 1):
        try:
            await producer.start()
            logger.info("Kafka producer started successfully (payment_service).")
            return
        except KafkaConnectionError:
            logger.info(f"Payment Service: Attempt {attempt}/{retries} - Kafka not ready. Retrying in {delay} seconds...")
            await asyncio.sleep(delay)
    raise KafkaConnectionError("Payment Service: Kafka not ready after several retries.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check if running in development mode (no Kafka)
    if os.getenv("SKIP_KAFKA", "false").lower() == "true":
        logger.info("Skipping Kafka setup for local development")
        yield
        return
    
    logger.info("Payment service lifespan starting...")
    
    await start_producer_with_retry(producer)
    logger.info("Producer started, now importing consumers...")
    
    # Import consumers here to avoid circular imports
    from payment_service.consumers import process_orders, refund_on_delivery_failure, process_payment_compensations
    
    logger.info("Starting consumer tasks...")
    consumer_task_order = asyncio.create_task(process_orders())
    consumer_task_refund = asyncio.create_task(refund_on_delivery_failure())
    consumer_task_compensation = asyncio.create_task(process_payment_compensations())
    
    logger.info("All consumer tasks started, payment service ready")
    
    yield
    
    logger.info("Shutting down payment service consumers...")
    consumer_task_order.cancel()
    consumer_task_refund.cancel()
    consumer_task_compensation.cancel()
    try:
        await consumer_task_order
    except asyncio.CancelledError:
        logger.info("Order consumer task cancelled")
    try:
        await consumer_task_refund
    except asyncio.CancelledError:
        logger.info("Refund consumer task cancelled")
    try:
        await consumer_task_compensation
    except asyncio.CancelledError:
        logger.info("Compensation consumer task cancelled")
    await producer.stop()
    logger.info("Payment service shutdown complete")
