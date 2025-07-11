import asyncio
import logging
from contextlib import asynccontextmanager
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError
from fastapi import FastAPI

KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)

# payment_service/config.py

DATABASE_URL = "postgresql://postgres:password@payment_db:5432/payment_db"
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"

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

from payment_service.consumers import process_orders, refund_on_delivery_failure

@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_producer_with_retry(producer)
    consumer_task_order = asyncio.create_task(process_orders())
    consumer_task_refund = asyncio.create_task(refund_on_delivery_failure())
    yield
    consumer_task_order.cancel()
    consumer_task_refund.cancel()
    try:
        await consumer_task_order
    except asyncio.CancelledError:
        pass
    try:
        await consumer_task_refund
    except asyncio.CancelledError:
        pass
    await producer.stop()
