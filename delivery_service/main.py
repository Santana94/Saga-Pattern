from fastapi import FastAPI
from delivery_service.settings import lifespan

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def read_root():
    return {"message": "Delivery service is running"}
