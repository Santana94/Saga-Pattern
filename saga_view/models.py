from sqlalchemy import create_engine, Column, String, Integer, DateTime, MetaData, Table, func, Text, Float
from sqlalchemy.orm import sessionmaker
from saga_view.settings import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metadata = MetaData()

sagas = Table(
    "sagas",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("saga_id", String, unique=True, index=True),
    Column("order_id", Integer, nullable=True),
    Column("order_status", String, nullable=True),
    Column("payment_status", String, nullable=True),
    Column("delivery_status", String, nullable=True),
    Column("saga_status", String, default="started"),  # started, completed, failed, compensating, compensated
    Column("item", String, nullable=True),
    Column("quantity", Integer, nullable=True),
    Column("price", Float, nullable=True),
    Column("created_at", DateTime, server_default=func.now()),
    Column("updated_at", DateTime, server_default=func.now(), onupdate=func.now()),
    Column("completion_reason", String, nullable=True),  # success, payment_failed, delivery_failed
    Column("error_message", Text, nullable=True)
)

saga_events = Table(
    "saga_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("saga_id", String, index=True),
    Column("event_type", String, nullable=False),
    Column("service", String, nullable=False),  # order, payment, delivery
    Column("event_data", Text, nullable=True),  # JSON string of event payload
    Column("timestamp", DateTime, server_default=func.now()),
    Column("sequence", Integer, nullable=False)  # Order of events in saga
)

metadata.create_all(engine)
