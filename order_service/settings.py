import asyncio
import logging
import os
from contextlib import asynccontextmanager
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from fastapi import FastAPI

# Use environment variables for configuration
KAFKA_HOST = os.getenv("KAFKA_HOST", "localhost")
KAFKA_PORT = os.getenv("KAFKA_PORT", "9092")
DB_HOST = os.getenv("DB_HOST", "localhost")

# Your Kafka bootstrap server
KAFKA_BOOTSTRAP_SERVERS = f"{KAFKA_HOST}:{KAFKA_PORT}"

# Create the producer instance
producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)

# payment_service/config.py

DATABASE_URL = f"postgresql://postgres:password@{DB_HOST}:15432/order_db"

logger = logging.getLogger(__name__)


# Helper function: create Kafka topics if they don't exist
async def create_topics():
    admin = AIOKafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    try:
        await admin.start()
        
        # Define topics needed for this service
        topics = [
            NewTopic(name="orders", num_partitions=1, replication_factor=1),
            NewTopic(name="order_compensations", num_partitions=1, replication_factor=1),
            NewTopic(name="payments", num_partitions=1, replication_factor=1),
            NewTopic(name="deliveries", num_partitions=1, replication_factor=1),
        ]
        
        # Try to create all topics - Kafka will ignore existing ones
        await admin.create_topics(topics)
        logger.info(f"Created/verified topics: {[t.name for t in topics]}")
            
    except Exception as e:
        logger.warning(f"Failed to create topics: {e}")
    finally:
        await admin.close()


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
    # Check if running in development mode (no Kafka)
    if os.getenv("SKIP_KAFKA", "false").lower() == "true":
        logger.info("Skipping Kafka setup for local development")
        yield
        return
    
    # Create topics first
    logger.info("Creating Kafka topics...")
    await create_topics()
    
    # Use the retry function to start the producer
    logger.info("Starting producer...")
    await start_producer_with_retry(producer)
    logger.info("Producer started successfully.")
    
    # Wait a bit for topics to be ready
    await asyncio.sleep(2)
    
    # Start the consumer task
    consumer_task = asyncio.create_task(order_event_consumer())
    yield
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await producer.stop()
