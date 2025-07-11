import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from payment_service.services import create_payment, refund_payment
from payment_service.settings import KAFKA_BOOTSTRAP_SERVERS

logger = logging.getLogger(__name__)


async def process_orders():
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="payment_service_group",
        auto_offset_reset="earliest"
    )
    await consumer.start()
    logger.info("Payment service consumer started.")
    try:
        async for msg in consumer:
            event = json.loads(msg.value.decode("utf-8"))
            logger.info(event)
            if event.get("type") == "OrderCreated":
                order_id = event.get("order_id")
                price = event.get("price")
                saga_id = event.get("saga_id")  # Extract saga_id from the event
                logger.info(f"Payment service processing order {order_id}, price {price} with saga_id {saga_id}")
                await asyncio.sleep(1)
                await create_payment(order_id, saga_id, price)
    finally:
        await consumer.stop()

async def refund_on_delivery_failure():
    consumer = AIOKafkaConsumer(
        "delivery_events",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="payment_service_refund_group",
        auto_offset_reset="earliest"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            event = json.loads(msg.value.decode("utf-8"))
            if event.get("type") == "DeliveryFailed":
                order_id = event.get("order_id")
                saga_id = event.get("saga_id")  # Propagate saga_id
                logger.info(f"Delivery failed for order {order_id} with saga_id {saga_id}, refunding payment.")
                await refund_payment(order_id, saga_id)
    finally:
        await consumer.stop()
