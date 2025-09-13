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
        # Simulate payment processing with higher success rate
        if random.choice([True, True, True, False]):
            payment_status = "processed"
            payment_event = {"type": "PaymentProcessed", "order_id": order_id, "saga_id": saga_id, "amount": price}
            logger.info(f"Payment processed for order {order_id}")
        else:
            payment_status = "failed"
            payment_event = {"type": "PaymentFailed", "order_id": order_id, "saga_id": saga_id, "amount": price}
            logger.info(f"Payment failed for order {order_id}")
        
        ins = payments.insert().values(order_id=order_id, amount=int(price * 100), status=payment_status)
        db.execute(ins)
        db.commit()

        # Send payment event to payments topic (for delivery service coordination)
        await producer.send_and_wait("payments", json.dumps(payment_event).encode("utf-8"))
        logger.info(f"Payment event {payment_event['type']} published for order {order_id}")
        
        # If payment failed, trigger order cancellation compensation
        if payment_status == "failed":
            cancel_event = {"type": "CancelOrder", "order_id": order_id, "saga_id": saga_id, "reason": "Payment failed"}
            await producer.send_and_wait("order_compensations", json.dumps(cancel_event).encode("utf-8"))
            logger.info(f"Order cancellation triggered for failed payment on order {order_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in payment service: {e}")
    finally:
        db.close()


async def refund_payment(order_id, saga_id):
    db = SessionLocal()
    try:
        stmt = update(payments).where(payments.c.order_id == order_id).values(status="refunded")
        db.execute(stmt)
        db.commit()
        
        # Send refund completion event
        refund_event = {"type": "PaymentRefunded", "order_id": order_id, "saga_id": saga_id}
        await producer.send_and_wait("payments", json.dumps(refund_event).encode("utf-8"))
        logger.info(f"Payment refunded for order {order_id}")
        
        # Trigger order cancellation as next step in compensation chain
        cancel_event = {"type": "CancelOrder", "order_id": order_id, "saga_id": saga_id, "reason": "Payment refunded due to delivery failure"}
        await producer.send_and_wait("order_compensations", json.dumps(cancel_event).encode("utf-8"))
        logger.info(f"Order cancellation triggered after payment refund for order {order_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during refund: {e}")
    finally:
        db.close()
