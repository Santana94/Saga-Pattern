import json
import logging

from aiokafka import AIOKafkaConsumer

from order_service.enums import PaymentCompensationEvents

logger = logging.getLogger(__name__)


# Consumer: listen for compensation events in choreographed saga
async def order_event_consumer():
    from order_service.settings import KAFKA_BOOTSTRAP_SERVERS
    from order_service.services import cancel_order
    
    logger.info(f"📝 order_event_consumer function called! KAFKA_BOOTSTRAP_SERVERS={KAFKA_BOOTSTRAP_SERVERS}")
    
    consumer = AIOKafkaConsumer(
        "order_compensations",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="order_service_group",
        auto_offset_reset="earliest"
    )
    
    logger.info("Consumer object created, attempting to start...")
    
    try:
        await consumer.start()
        logger.info(f"✅ Order service consumer started successfully, listening to 'order_compensations' topic on {KAFKA_BOOTSTRAP_SERVERS}")
        logger.info("Order service consumer waiting for messages...")
        
        # Add a heartbeat log every 30 seconds to show it's alive
        async def heartbeat():
            import asyncio
            while True:
                await asyncio.sleep(30)
                logger.info("💓 Order consumer heartbeat - still waiting for messages")
        
        import asyncio
        heartbeat_task = asyncio.create_task(heartbeat())
        
        try:
            async for msg in consumer:
                try:
                    logger.info(f"📨 Order service received raw message: topic={msg.topic}, partition={msg.partition}, offset={msg.offset}")
                    event = json.loads(msg.value.decode("utf-8"))
                    logger.info(f"📨 Order service received compensation event: {event}")
                    
                    if event.get("type") == "CancelOrder":
                        # Perform compensation: cancel the order
                        order_id = event.get("order_id")
                        saga_id = event.get("saga_id")
                        logger.info(f"📝 Cancelling order {order_id} for saga {saga_id}")
                        await cancel_order(order_id, saga_id)
                    else:
                        logger.info(f"🚫 Ignoring event of type: {event.get('type')}")
                        
                except Exception as e:
                    logger.error(f"❌ Error processing message: {e}")
        finally:
            heartbeat_task.cancel()
                    
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR in order service consumer: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
    finally:
        await consumer.stop()
        logger.info("🔴 Order service consumer stopped")
