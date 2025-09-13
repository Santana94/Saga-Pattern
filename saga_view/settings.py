import asyncio
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from aiokafka.admin import AIOKafkaAdminClient, NewTopic

# Use environment variables for configuration
KAFKA_HOST = os.getenv("KAFKA_HOST", "localhost")
KAFKA_PORT = os.getenv("KAFKA_PORT", "9092")
DB_HOST = os.getenv("DB_HOST", "localhost")

KAFKA_BOOTSTRAP_SERVERS = f"{KAFKA_HOST}:{KAFKA_PORT}"
DATABASE_URL = f"postgresql://postgres:password@{DB_HOST}:15435/saga_db"

logger = logging.getLogger(__name__)

# Helper function: create Kafka topics if they don't exist
async def create_topics():
    admin = AIOKafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    try:
        await admin.start()
        
        # Define all topics needed for saga view
        topics = [
            NewTopic(name="orders", num_partitions=1, replication_factor=1),
            NewTopic(name="payments", num_partitions=1, replication_factor=1),
            NewTopic(name="delivery_events", num_partitions=1, replication_factor=1),
            NewTopic(name="order_compensations", num_partitions=1, replication_factor=1),
            NewTopic(name="payment_compensations", num_partitions=1, replication_factor=1),
            NewTopic(name="delivery_compensations", num_partitions=1, replication_factor=1),
        ]
        
        # Try to create all topics - Kafka will ignore existing ones
        await admin.create_topics(topics)
        logger.info(f"Created/verified topics: {[t.name for t in topics]}")
            
    except Exception as e:
        logger.warning(f"Failed to create topics: {e}")
    finally:
        await admin.close()

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
    
    # Wait a bit for topics to be ready
    await asyncio.sleep(2)
    
    from saga_view.consumers import process_saga_events
    consumer_task = asyncio.create_task(process_saga_events())
    yield
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
