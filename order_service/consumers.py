import json
import logging

from aiokafka import AIOKafkaConsumer

from order_service.enums import PaymentCompensationEvents

logger = logging.getLogger(__name__)


# Consumer: listen for compensation events (PaymentFailed, PaymentRefunded)
async def order_event_consumer():
    from order_service.settings import KAFKA_BOOTSTRAP_SERVERS
    from order_service.services import cancel_order
    consumer = AIOKafkaConsumer(
        "order_compensations",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="order_service_group",
        auto_offset_reset="earliest"
    )
    logger.info("Order service consumer started.")
    await consumer.start()
    try:
        async for msg in consumer:
            event = json.loads(msg.value.decode("utf-8"))
            logger.info("Order service received compensation event:", event)
            if event.get("type") in PaymentCompensationEvents:
                # Perform compensation: cancel the order.
                order_id = event.get("order_id")
                cancel_order(order_id)
    finally:
        await consumer.stop()
