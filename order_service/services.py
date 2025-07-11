import json
import logging
import uuid

from order_service.dtos import OrderDTO
from order_service.models import orders, SessionLocal
from order_service.settings import producer

logger = logging.getLogger(__name__)


def cancel_order(order_id):
    db = SessionLocal()
    try:
        db.execute(orders.update().where(orders.c.id == order_id).values(status="cancelled"))
        db.commit()
        logger.info(f"Order {order_id} cancelled due to compensation.")
    finally:
        db.close()


async def create_order(order: OrderDTO):
    db = SessionLocal()
    try:
        ins = orders.insert().values(item=order.item, quantity=order.quantity, status="created", price=order.price)
        result = db.execute(ins)
        db.commit()
        order_id = result.inserted_primary_key[0]

        # Publish OrderCreated event.
        saga_id = str(uuid.uuid4())
        event = {
            "type": "OrderCreated",
            "order_id": order_id,
            "item": order.item,
            "quantity": order.quantity,
            "price": order.price,
            "saga_id": saga_id
        }
        logger.info(f"Order {order_id} created.")
        await producer.send_and_wait("orders", json.dumps(event).encode("utf-8"))
        logger.info(f"Event {event} published to Kafka.")

        return order_id
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
