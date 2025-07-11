import asyncio
import json
from aiokafka import AIOKafkaConsumer
from saga_view.settings import KAFKA_BOOTSTRAP_SERVERS
from saga_view.models import sagas, SessionLocal
from sqlalchemy import update
import logging

logger = logging.getLogger(__name__)

# Subscribe to all topics that emit saga-related events.
KAFKA_TOPICS = ["orders", "payments", "delivery_events", "order_compensations"]


async def process_saga_events():
    consumer = AIOKafkaConsumer(
        *KAFKA_TOPICS,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="saga_view_group",
        auto_offset_reset="earliest",
    )
    await consumer.start()
    try:
        async for msg in consumer:
            try:
                event = json.loads(msg.value.decode("utf-8"))
                logger.info("Saga View received event: %s", event)
                saga_id = event.get("saga_id")
                if not saga_id:
                    logger.warning("Event skipped; no saga_id found: %s", event)
                    continue

                event_type = event.get("type")
                db = SessionLocal()
                try:
                    # Fetch an existing saga record, or create a new one if not present.
                    result = db.execute(sagas.select().where(sagas.c.saga_id == saga_id)).fetchone()
                    if result is None:
                        ins = sagas.insert().values(saga_id=saga_id)
                        db.execute(ins)
                        db.commit()

                    update_values = {}
                    if event_type == "OrderCreated":
                        update_values["order_status"] = "created"
                    elif event_type == "PaymentProcessed":
                        update_values["payment_status"] = "processed"
                    elif event_type == "PaymentFailed":
                        update_values["payment_status"] = "failed"
                    elif event_type == "PaymentRefunded":
                        update_values["payment_status"] = "refunded"
                    elif event_type == "DeliveryScheduled":
                        update_values["delivery_status"] = "scheduled"
                    elif event_type == "DeliveryFailed":
                        update_values["delivery_status"] = "failed"
                    elif event_type == "OrderCancelled":
                        update_values["order_status"] = "cancelled"

                    if update_values:
                        stmt = update(sagas).where(sagas.c.saga_id == saga_id).values(**update_values)
                        db.execute(stmt)
                        db.commit()
                except Exception as e:
                    db.rollback()
                    logger.error("DB error while processing saga event: %s", e)
                finally:
                    db.close()
            except Exception as e:
                logger.error("Error processing event: %s", e)
    finally:
        await consumer.stop()
