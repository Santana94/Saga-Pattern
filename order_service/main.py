from fastapi import FastAPI

from order_service import services
from order_service.dtos import OrderDTO
from order_service.settings import lifespan

app = FastAPI(lifespan=lifespan)


@app.post("/orders")
async def create_order(order: OrderDTO):
    order_id = await services.create_order(order)

    return {"order_id": order_id, "status": "created"}
