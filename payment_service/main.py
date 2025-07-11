from fastapi import FastAPI
from payment_service.settings import lifespan

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def read_root():
    return {"message": "Payment service is running"}
