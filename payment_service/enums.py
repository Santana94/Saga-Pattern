from enum import Enum


class PaymentEventTypes(Enum):
    PAYMENT_PROCESSED = "PaymentProcessed"
    PAYMENT_FAILED = "PaymentFailed"
    PAYMENT_REFUNDED = "PaymentRefunded"


class PaymentCompensationEvents(Enum):
    payment_failed = "payment_failed"
    payment_refunded = "payment_refunded"
