from pydantic import BaseModel

class OrderDTO(BaseModel):
    item: str
    quantity: int
    price: float
