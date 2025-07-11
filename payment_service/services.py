import json
import logging
import random

from payment_service.models import payments, SessionLocal
from payment_service.settings import producer
from sqlalchemy import update

logger = logging.getLogger(__name__)


async def create_payment(order_id, saga_id, price):
    db = SessionLocal()
    try:
        if random.choice([True, False]):
            payment_status = "processed"
            payment_event = {"type": "PaymentProcessed", "order_id": order_id, "saga_id": saga_id, "price": price}
            logger.info(f"Payment processed for order {order_id}")
        else:
            payment_status = "failed"
            payment_event = {"type": "PaymentFailed", "order_id": order_id, "saga_id": saga_id, "price": price}
            logger.info(f"Payment failed for order {order_id}")
        ins = payments.insert().values(order_id=order_id, status=payment_status)
        db.execute(ins)
        db.commit()

        # Emit compensation event and, if processed, also forward for delivery.
        await producer.send_and_wait("order_compensations", json.dumps(payment_event).encode("utf-8"))
        if payment_event["type"] == "PaymentProcessed":
            logger.info(f"Payment processed for order {order_id}")
            await producer.send_and_wait("payments", json.dumps(payment_event).encode("utf-8"))
            logger.info(f"Payment processed for order {order_id}")
    except Exception as e:
        db.rollback()
        logger.info("Error in payment service:", e)
    finally:
        db.close()


async def refund_payment(order_id, saga_id):
    refund_event = {"type": "PaymentRefunded", "order_id": order_id, "saga_id": saga_id}
    db = SessionLocal()
    try:
        stmt = update(payments).where(payments.c.order_id == order_id).values(status="refunded")
        db.execute(stmt)
        db.commit()
        await producer.send_and_wait("order_compensations", json.dumps(refund_event).encode("utf-8"))
    except Exception as e:
        db.rollback()
        print("Error during refund:", e)
    finally:
        db.close()
