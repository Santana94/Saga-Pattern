import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from payment_service.services import create_payment, refund_payment
from payment_service.settings import KAFKA_BOOTSTRAP_SERVERS

logger = logging.getLogger(__name__)


async def process_orders():
    logger.info(f"process_orders function called! KAFKA_BOOTSTRAP_SERVERS={KAFKA_BOOTSTRAP_SERVERS}")
    
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="payment_service_group",
        auto_offset_reset="earliest"
    )
    
    logger.info("Consumer object created, attempting to start...")
    
    try:
        await consumer.start()
        logger.info(f"✅ Payment service consumer started successfully, listening to 'orders' topic on {KAFKA_BOOTSTRAP_SERVERS}")
        logger.info("Payment service consumer waiting for messages...")
        
        # Add a heartbeat log every 30 seconds to show it's alive
        async def heartbeat():
            while True:
                await asyncio.sleep(30)
                logger.info("💓 Payment consumer heartbeat - still waiting for messages")
        
        heartbeat_task = asyncio.create_task(heartbeat())
        
        try:
            async for msg in consumer:
                try:
                    logger.info(f"📨 Payment service received raw message: topic={msg.topic}, partition={msg.partition}, offset={msg.offset}")
                    event = json.loads(msg.value.decode("utf-8"))
                    logger.info(f"📨 Payment service received event: {event}")
                    
                    if event.get("type") == "OrderCreated":
                        order_id = event.get("order_id")
                        price = event.get("price")
                        saga_id = event.get("saga_id")
                        logger.info(f"💳 Processing payment for order {order_id}, price {price} with saga_id {saga_id}")
                        await asyncio.sleep(1)
                        await create_payment(order_id, saga_id, price)
                    else:
                        logger.info(f"🚫 Ignoring event of type: {event.get('type')}")
                        
                except Exception as e:
                    logger.error(f"❌ Error processing message: {e}")
        finally:
            heartbeat_task.cancel()
                
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR in payment service consumer: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
    finally:
        await consumer.stop()
        logger.info("🔴 Payment service consumer stopped")

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


async def process_payment_compensations():
    """Handle payment compensation requests in choreographed saga"""
    consumer = AIOKafkaConsumer(
        "payment_compensations",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="payment_compensation_group",
        auto_offset_reset="earliest"
    )
    await consumer.start()
    logger.info("Payment compensation consumer started (choreographed saga).")
    try:
        async for msg in consumer:
            event = json.loads(msg.value.decode("utf-8"))
            logger.info(f"Payment service received compensation event: {event}")
            if event.get("type") == "RefundPayment":
                order_id = event.get("order_id")
                saga_id = event.get("saga_id")
                logger.info(f"Processing refund for order {order_id} with saga_id {saga_id}")
                await refund_payment(order_id, saga_id)
    finally:
        await consumer.stop()
