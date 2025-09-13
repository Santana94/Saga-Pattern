import asyncio
import json
import random
import logging
from aiokafka import AIOKafkaConsumer
from delivery_service.settings import KAFKA_BOOTSTRAP_SERVERS, producer
from delivery_service.models import deliveries, SessionLocal

logger = logging.getLogger(__name__)

async def process_payments_for_delivery():
    logger.info(f"🚚 process_payments_for_delivery function called! KAFKA_BOOTSTRAP_SERVERS={KAFKA_BOOTSTRAP_SERVERS}")
    
    consumer = AIOKafkaConsumer(
        "payments",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="delivery_service_group",
        auto_offset_reset="earliest"
    )
    
    logger.info("Consumer object created, attempting to start...")
    
    try:
        await consumer.start()
        logger.info(f"✅ Delivery service consumer started successfully, listening to 'payments' topic on {KAFKA_BOOTSTRAP_SERVERS}")
        logger.info("Delivery service consumer waiting for messages...")
        
        # Add a heartbeat log every 30 seconds to show it's alive
        async def heartbeat():
            while True:
                await asyncio.sleep(30)
                logger.info("💓 Delivery consumer heartbeat - still waiting for messages")
        
        heartbeat_task = asyncio.create_task(heartbeat())
        
        try:
            async for msg in consumer:
                try:
                    logger.info(f"📨 Delivery service received raw message: topic={msg.topic}, partition={msg.partition}, offset={msg.offset}")
                    event = json.loads(msg.value.decode("utf-8"))
                    logger.info(f"📨 Delivery service received event: {event}")
                    
                    if event.get("type") == "PaymentProcessed":
                        order_id = event.get("order_id")
                        saga_id = event.get("saga_id")
                        logger.info(f"🚚 Processing delivery for order {order_id} with saga_id {saga_id}")
                        await asyncio.sleep(1)
                        db = SessionLocal()
                        try:
                            # Simulate delivery scheduling with some chance of failure
                            if random.choice([True, True, False]):
                                delivery_status = "scheduled"
                                delivery_event = {"type": "DeliveryScheduled", "order_id": order_id, "saga_id": saga_id}
                                logger.info(f"✅ Delivery scheduled for order {order_id}")
                            else:
                                delivery_status = "failed"
                                delivery_event = {"type": "DeliveryFailed", "order_id": order_id, "saga_id": saga_id}
                                logger.info(f"❌ Delivery failed for order {order_id}")
                            
                            ins = deliveries.insert().values(order_id=order_id, status=delivery_status)
                            db.execute(ins)
                            db.commit()
                            
                            # Publish delivery event
                            await producer.send_and_wait("delivery_events", json.dumps(delivery_event).encode("utf-8"))
                            
                            # If delivery failed, trigger payment refund compensation
                            if delivery_status == "failed":
                                refund_event = {"type": "RefundPayment", "order_id": order_id, "saga_id": saga_id, "reason": "Delivery failed"}
                                await producer.send_and_wait("payment_compensations", json.dumps(refund_event).encode("utf-8"))
                                logger.info(f"💰 Payment refund triggered for failed delivery on order {order_id}")
                                
                        except Exception as e:
                            db.rollback()
                            logger.error(f"❌ DB error in delivery service: {e}")
                        finally:
                            db.close()
                    else:
                        logger.info(f"🚫 Ignoring event of type: {event.get('type')}")
                        
                except Exception as e:
                    logger.error(f"❌ Error processing message: {e}")
        finally:
            heartbeat_task.cancel()
                
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR in delivery service consumer: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
    finally:
        await consumer.stop()
        logger.info("🔴 Delivery service consumer stopped")


async def process_delivery_compensations():
    """Handle delivery cancellation requests in choreographed saga"""
    consumer = AIOKafkaConsumer(
        "delivery_compensations",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="delivery_compensation_group",
        auto_offset_reset="earliest"
    )
    await consumer.start()
    logger.info("Delivery compensation consumer started (choreographed saga).")
    try:
        async for msg in consumer:
            event = json.loads(msg.value.decode("utf-8"))
            logger.info(f"Delivery service received compensation event: {event}")
            if event.get("type") == "CancelDelivery":
                order_id = event.get("order_id")
                saga_id = event.get("saga_id")
                logger.info(f"Cancelling delivery for order {order_id} with saga_id {saga_id}")
                
                db = SessionLocal()
                try:
                    # Update delivery status to cancelled
                    update_stmt = deliveries.update().where(
                        deliveries.c.order_id == order_id
                    ).values(status="cancelled")
                    db.execute(update_stmt)
                    db.commit()
                    
                    # Send compensation completion event
                    compensation_event = {
                        "type": "DeliveryCancelled", 
                        "order_id": order_id, 
                        "saga_id": saga_id
                    }
                    await producer.send_and_wait(
                        "delivery_events", 
                        json.dumps(compensation_event).encode("utf-8")
                    )
                    logger.info(f"Delivery cancelled for order {order_id}")
                    
                except Exception as e:
                    db.rollback()
                    logger.error(f"Error cancelling delivery for order {order_id}: {e}")
                finally:
                    db.close()
    finally:
        await consumer.stop()
