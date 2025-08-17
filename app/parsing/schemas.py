from pydantic import BaseModel, Field
from typing import Literal, List, Optional

class ParsedItem(BaseModel):
    name: str
    sku: Optional[str] = None
    qty: int = Field(gt=0, default=1)
    unit_price: Optional[float] = None
    rent_monthly: Optional[float] = None
    buyback_rate: Optional[float] = None

class ParsedDelivery(BaseModel):
    outbound_fee: float = 0.0
    return_fee: float = 0.0
    prepaid_outbound: bool = True
    prepaid_return: bool = False

class ParsedSchedule(BaseModel):
    date: Optional[str] = None
    time: Optional[str] = None

class ParsedOrder(BaseModel):
    code: str
    type: Literal["OUTRIGHT","INSTALMENT","RENTAL"]
    customer_name: str
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None
    schedule: Optional[ParsedSchedule] = None
    items: List[ParsedItem]
    delivery: ParsedDelivery
    total: Optional[float] = None
    monthly_amount: Optional[float] = None
    plan_months: Optional[int] = None
