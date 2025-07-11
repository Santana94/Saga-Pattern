from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table, Float
from sqlalchemy.orm import sessionmaker

from order_service.settings import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metadata = MetaData()

orders = Table(
    "orders",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("item", String),
    Column("quantity", Integer),
    Column("price", Float),
    Column("status", String, default="created"),
)
metadata.create_all(engine)
