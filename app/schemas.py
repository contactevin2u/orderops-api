from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
from datetime import date

class ItemIn(BaseModel):
    sku: Optional[str] = None
    name: str
    qty: int = Field(gt=0)
    unit_price: Optional[float] = None
    rent_monthly: Optional[float] = None
    buyback_rate: Optional[float] = None

class DeliveryIn(BaseModel):
    outbound_fee: float = 0.0
    return_fee: float = 0.0
    prepaid_outbound: bool = True
    prepaid_return: bool = False

class ScheduleIn(BaseModel):
    date: Optional[date] = None
    time: Optional[str] = None

class CustomerIn(BaseModel):
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None

class OrderCreate(BaseModel):
    code: str
    type: Literal["OUTRIGHT","INSTALMENT","RENTAL"]
    customer: CustomerIn
    plan_months: Optional[int] = None
    plan_monthly_amount: Optional[float] = None
    plan_start_date: Optional[date] = None
    schedule: Optional[ScheduleIn] = None
    items: List[ItemIn]
    delivery: DeliveryIn

class PaymentIn(BaseModel):
    amount: float = Field(gt=0)
    method: Optional[str] = "CASH"

class EventIn(BaseModel):
    event: Literal["RETURN","COLLECT","INSTALMENT_CANCEL","BUYBACK"]
    penalty: Optional[float] = None
    delivery_return_fee: Optional[float] = None
    buyback_rate: Optional[float] = None

class ParseIn(BaseModel):
    text: str
    matcher: Literal["ai","rapidfuzz","hybrid"] = "hybrid"
    lang: Literal["en","ms"] = "en"
