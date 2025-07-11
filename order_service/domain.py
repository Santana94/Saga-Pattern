from pydantic import BaseModel

class Order(BaseModel):
    item: str
    quantity: int
    status: str
