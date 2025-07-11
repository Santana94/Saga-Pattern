from fastapi import FastAPI, HTTPException
from saga_view.settings import lifespan
from saga_view.models import sagas, SessionLocal
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(lifespan=lifespan)

class SagaView(BaseModel):
    saga_id: str
    order_status: Optional[str]
    payment_status: Optional[str]
    delivery_status: Optional[str]

@app.get("/sagas", response_model=List[SagaView])
def get_all_sagas():
    db = SessionLocal()
    try:
        results = db.execute(sagas.select()).fetchall()
        saga_list = []
        for row in results:
            saga_list.append(SagaView(
                saga_id=row["saga_id"],
                order_status=row.get("order_status"),
                payment_status=row.get("payment_status"),
                delivery_status=row.get("delivery_status")
            ))
        return saga_list
    finally:
        db.close()

@app.get("/sagas/{saga_id}", response_model=SagaView)
def get_saga(saga_id: str):
    db = SessionLocal()
    try:
        row = db.execute(sagas.select().where(sagas.c.saga_id == saga_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Saga not found")
        return SagaView(
            saga_id=row["saga_id"],
            order_status=row.get("order_status"),
            payment_status=row.get("payment_status"),
            delivery_status=row.get("delivery_status")
        )
    finally:
        db.close()
