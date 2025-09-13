import json
import logging
import uuid

from order_service.dtos import OrderDTO
from order_service.models import orders, SessionLocal
from order_service.settings import producer

logger = logging.getLogger(__name__)


async def cancel_order(order_id, saga_id):
    db = SessionLocal()
    try:
        db.execute(orders.update().where(orders.c.id == order_id).values(status="cancelled"))
        db.commit()
        logger.info(f"Order {order_id} cancelled due to compensation.")
        
        # Publish OrderCancelled event
        event = {
            "type": "OrderCancelled",
            "order_id": order_id,
            "saga_id": saga_id
        }
        await producer.send_and_wait("orders", json.dumps(event).encode("utf-8"))
        logger.info(f"Order cancellation event published for order {order_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling order {order_id}: {e}")
        raise e
    finally:
        db.close()


async def create_order(order: OrderDTO):
    """Create order and trigger choreographed saga"""
    db = SessionLocal()
    try:
        ins = orders.insert().values(item=order.item, quantity=order.quantity, status="created", price=order.price)
        result = db.execute(ins)
        db.commit()
        order_id = result.inserted_primary_key[0]

        # Publish OrderCreated event to trigger choreographed saga
        saga_id = str(uuid.uuid4())
        event = {
            "type": "OrderCreated",
            "order_id": order_id,
            "item": order.item,
            "quantity": order.quantity,
            "price": order.price,
            "saga_id": saga_id
        }
        logger.info(f"Order {order_id} created with saga_id {saga_id}")
        await producer.send_and_wait("orders", json.dumps(event).encode("utf-8"))
        logger.info(f"OrderCreated event published to trigger saga {saga_id}")

        return order_id
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
