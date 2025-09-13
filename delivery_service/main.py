import logging
from fastapi import FastAPI
from delivery_service.settings import lifespan

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Delivery service main.py loading...")

app = FastAPI(lifespan=lifespan)

logger.info("FastAPI app created with lifespan")

@app.get("/")
async def read_root():
    logger.info("Health check endpoint called")
    return {"message": "Delivery service is running"}

@app.on_event("startup")
async def startup_event():
    logger.info("Delivery service startup event triggered")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting delivery service on port 8002...")
    uvicorn.run(app, host="127.0.0.1", port=8002)
