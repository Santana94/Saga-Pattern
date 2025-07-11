import asyncio
import json
import random
import logging
from aiokafka import AIOKafkaConsumer
from delivery_service.settings import KAFKA_BOOTSTRAP_SERVERS, producer
from delivery_service.models import deliveries, SessionLocal

logger = logging.getLogger(__name__)

async def process_payments_for_delivery():
    consumer = AIOKafkaConsumer(
        "payments",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="delivery_service_group",
        auto_offset_reset="earliest"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            event = json.loads(msg.value.decode("utf-8"))
            if event.get("type") == "PaymentProcessed":
                order_id = event.get("order_id")
                saga_id = event.get("saga_id")  # Extract saga_id from the payment event
                print(f"Delivery service processing order {order_id} with saga_id {saga_id}")
                await asyncio.sleep(1)
                db = SessionLocal()
                try:
                    if random.choice([True, True, False]):
                        delivery_status = "scheduled"
                        delivery_event = {"type": "DeliveryScheduled", "order_id": order_id, "saga_id": saga_id}
                        logger.info(f"Delivery scheduled for order {order_id}")
                    else:
                        delivery_status = "failed"
                        delivery_event = {"type": "DeliveryFailed", "order_id": order_id, "saga_id": saga_id}
                        logger.info(f"Delivery failed for order {order_id}")
                    ins = deliveries.insert().values(order_id=order_id, status=delivery_status)
                    db.execute(ins)
                    db.commit()
                except Exception as e:
                    db.rollback()
                    print("DB error in delivery service:", e)
                finally:
                    db.close()
                await producer.send_and_wait("delivery_events", json.dumps(delivery_event).encode("utf-8"))
    finally:
        await consumer.stop()
