import logging
from fastapi import FastAPI
from payment_service.settings import lifespan

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Payment service main.py loading...")

app = FastAPI(lifespan=lifespan)

logger.info("FastAPI app created with lifespan")

@app.get("/")
async def read_root():
    logger.info("Health check endpoint called")
    return {"message": "Payment service is running"}

@app.on_event("startup")
async def startup_event():
    logger.info("Payment service startup event triggered")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting payment service on port 8001...")
    uvicorn.run(app, host="127.0.0.1", port=8001)
