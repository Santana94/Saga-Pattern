import asyncio
import json
from datetime import datetime
from aiokafka import AIOKafkaConsumer
from saga_view.settings import KAFKA_BOOTSTRAP_SERVERS
from saga_view.models import sagas, saga_events, SessionLocal
from sqlalchemy import update, func
import logging

logger = logging.getLogger(__name__)

# Subscribe to all topics that emit saga-related events
KAFKA_TOPICS = [
    "orders", 
    "payments", 
    "delivery_events", 
    "order_compensations", 
    "payment_compensations", 
    "delivery_compensations"
]


class SagaEventProcessor:
    def __init__(self):
        self.event_sequence = {}  # Track sequence per saga
    
    def get_service_from_topic(self, topic):
        """Determine service from Kafka topic"""
        if topic == "orders" or topic == "order_compensations":
            return "order"
        elif topic == "payments" or topic == "payment_compensations":
            return "payment"
        elif topic == "delivery_events" or topic == "delivery_compensations":
            return "delivery"
        return "unknown"
    
    def determine_saga_status(self, order_status, payment_status, delivery_status):
        """Determine overall saga status based on individual service statuses"""
        # If any service failed and compensation is happening
        if (order_status == "cancelled" or 
            payment_status in ["failed", "refunded"] or 
            delivery_status == "failed"):
            
            if order_status == "cancelled":
                return "compensated" if payment_status == "refunded" else "compensating"
            elif payment_status == "failed":
                return "failed"
            elif delivery_status == "failed":
                return "compensating"
                
        # Happy path
        elif (order_status == "created" and 
              payment_status == "processed" and 
              delivery_status == "scheduled"):
            return "completed"
            
        # In progress
        elif order_status == "created":
            return "in_progress"
            
        return "started"
    
    def get_completion_reason(self, order_status, payment_status, delivery_status):
        """Determine why the saga completed"""
        if payment_status == "failed":
            return "payment_failed"
        elif delivery_status == "failed":
            return "delivery_failed"
        elif (order_status == "created" and 
              payment_status == "processed" and 
              delivery_status == "scheduled"):
            return "success"
        return None

    async def process_event(self, event, topic):
        """Process a single saga event"""
        saga_id = event.get("saga_id")
        if not saga_id:
            logger.warning(f"Event skipped; no saga_id found: {event}")
            return

        event_type = event.get("type")
        service = self.get_service_from_topic(topic)
        
        # Track event sequence
        if saga_id not in self.event_sequence:
            self.event_sequence[saga_id] = 0
        self.event_sequence[saga_id] += 1
        
        db = SessionLocal()
        try:
            # Record the event in saga_events table
            event_insert = saga_events.insert().values(
                saga_id=saga_id,
                event_type=event_type,
                service=service,
                event_data=json.dumps(event),
                sequence=self.event_sequence[saga_id]
            )
            db.execute(event_insert)
            
            # Get or create saga record
            result = db.execute(sagas.select().where(sagas.c.saga_id == saga_id)).fetchone()
            
            if result is None:
                # Create new saga record with initial data from OrderCreated event
                initial_values = {"saga_id": saga_id}
                if event_type == "OrderCreated":
                    initial_values.update({
                        "order_id": event.get("order_id"),
                        "item": event.get("item"),
                        "quantity": event.get("quantity"),
                        "price": event.get("price"),
                        "order_status": "created"
                    })
                
                ins = sagas.insert().values(**initial_values)
                db.execute(ins)
                db.commit()
                
                # Refresh to get the created record
                result = db.execute(sagas.select().where(sagas.c.saga_id == saga_id)).fetchone()

            # Update saga status based on event
            update_values = {}
            
            if event_type == "OrderCreated":
                update_values.update({
                    "order_id": event.get("order_id"),
                    "item": event.get("item"),
                    "quantity": event.get("quantity"),
                    "price": event.get("price"),
                    "order_status": "created"
                })
            elif event_type == "OrderCancelled":
                update_values["order_status"] = "cancelled"
            elif event_type == "PaymentProcessed":
                update_values["payment_status"] = "processed"
            elif event_type == "PaymentFailed":
                update_values["payment_status"] = "failed"
                update_values["error_message"] = "Payment processing failed"
            elif event_type == "PaymentRefunded":
                update_values["payment_status"] = "refunded"
            elif event_type == "DeliveryScheduled":
                update_values["delivery_status"] = "scheduled"
            elif event_type == "DeliveryFailed":
                update_values["delivery_status"] = "failed"
                update_values["error_message"] = "Delivery scheduling failed"
            elif event_type == "DeliveryCancelled":
                update_values["delivery_status"] = "cancelled"

            # Determine overall saga status
            current_order_status = update_values.get("order_status", result.order_status)
            current_payment_status = update_values.get("payment_status", result.payment_status)
            current_delivery_status = update_values.get("delivery_status", result.delivery_status)
            
            saga_status = self.determine_saga_status(
                current_order_status, 
                current_payment_status, 
                current_delivery_status
            )
            update_values["saga_status"] = saga_status
            
            completion_reason = self.get_completion_reason(
                current_order_status,
                current_payment_status, 
                current_delivery_status
            )
            if completion_reason:
                update_values["completion_reason"] = completion_reason

            if update_values:
                stmt = update(sagas).where(sagas.c.saga_id == saga_id).values(**update_values)
                db.execute(stmt)
                db.commit()
                
                logger.info(f"Saga {saga_id} updated: {event_type} -> Status: {saga_status}")

        except Exception as e:
            db.rollback()
            logger.error(f"DB error while processing saga event: {e}")
        finally:
            db.close()


async def process_saga_events():
    """Main consumer function to process all saga events"""
    logger.info(f"🔍 process_saga_events function called! KAFKA_BOOTSTRAP_SERVERS={KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"🔍 Will listen to topics: {KAFKA_TOPICS}")
    
    processor = SagaEventProcessor()
    
    consumer = AIOKafkaConsumer(
        *KAFKA_TOPICS,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="saga_view_group",
        auto_offset_reset="earliest",
    )
    
    logger.info("Consumer object created, attempting to start...")
    
    try:
        await consumer.start()
        logger.info(f"✅ Saga View consumer started successfully, listening to topics: {KAFKA_TOPICS} on {KAFKA_BOOTSTRAP_SERVERS}")
        logger.info("Saga View consumer waiting for messages...")
        
        # Add a heartbeat log every 30 seconds to show it's alive
        async def heartbeat():
            while True:
                await asyncio.sleep(30)
                logger.info("💓 Saga View consumer heartbeat - still waiting for messages")
        
        heartbeat_task = asyncio.create_task(heartbeat())
        
        try:
            async for msg in consumer:
                try:
                    logger.info(f"📨 Saga View received raw message: topic={msg.topic}, partition={msg.partition}, offset={msg.offset}")
                    event = json.loads(msg.value.decode("utf-8"))
                    topic = msg.topic
                    logger.info(f"📨 Saga View received event from {topic}: {event}")
                    
                    await processor.process_event(event, topic)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing event: {e}")
        finally:
            heartbeat_task.cancel()
                    
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR in saga view consumer: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
    finally:
        await consumer.stop()
        logger.info("🔴 Saga View consumer stopped")
