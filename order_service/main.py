from fastapi import FastAPI
import logging

from order_service import services
from order_service.dtos import OrderDTO
from order_service.settings import lifespan

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Order service main.py loading...")

app = FastAPI(title="Order Service", lifespan=lifespan)

logger.info("FastAPI app created with lifespan")

@app.post("/orders")
async def create_order(order: OrderDTO):
    """Create an order and start choreographed saga"""
    try:
        order_id = await services.create_order(order)
        return {
            "order_id": order_id, 
            "status": "created",
            "message": "Order created successfully - saga coordination started"
        }
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        raise e

@app.get("/")
async def health_check():
    logger.info("Health check endpoint called")
    return {"service": "order_service", "status": "healthy"}

@app.on_event("startup")
async def startup_event():
    logger.info("Order service startup event triggered")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting order service on port 8000...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
