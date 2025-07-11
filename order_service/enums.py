from enum import Enum


class PaymentCompensationEvents(Enum):
    payment_failed = "payment_failed"
    payment_refunded = "payment_refunded"
