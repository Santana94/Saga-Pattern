from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table
from sqlalchemy.orm import sessionmaker
from delivery_service.settings import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metadata = MetaData()

deliveries = Table(
    "deliveries",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("order_id", Integer, unique=True, index=True),
    Column("status", String)
)
metadata.create_all(engine)
