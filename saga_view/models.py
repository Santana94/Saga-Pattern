from sqlalchemy import create_engine, Column, String, Integer, DateTime, MetaData, Table, func
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
    Column("order_status", String, nullable=True),
    Column("payment_status", String, nullable=True),
    Column("delivery_status", String, nullable=True),
    Column("updated_at", DateTime, server_default=func.now(), onupdate=func.now())
)
metadata.create_all(engine)
