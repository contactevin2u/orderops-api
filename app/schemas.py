from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

class ItemIn(BaseModel):
    text: Optional[str] = None
    item_type: Literal["OUTRIGHT", "RENTAL", "INSTALMENT"]
    sku: Optional[str] = None
    name: Optional[str] = None
    qty: Optional[float] = 1
    unit_price: Optional[float] = 0
    line_total: Optional[float] = 0
    months: Optional[int] = None
    monthly_amount: Optional[float] = None

class ParsedOrder(BaseModel):
    order_code: Optional[str] = None
    event_type: Optional[Literal["DELIVERY", "RETURN", "INSTALMENT_CANCEL", "BUYBACK", "ADJUSTMENT"]] = "DELIVERY"
    delivery_date: Optional[datetime] = None
    return_date: Optional[datetime] = None

    customer_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    location_url: Optional[str] = None

    items: List[ItemIn] = Field(default_factory=list)

    subtotal: Optional[float] = 0
    discount: Optional[float] = 0
    delivery_fee: Optional[float] = 0
    return_delivery_fee: Optional[float] = 0
    penalty_amount: Optional[float] = 0
    buyback_amount: Optional[float] = 0
    total: Optional[float] = 0
    paid: Optional[float] = 0
    to_collect: Optional[float] = 0
    notes: Optional[str] = None

class OrderItemOut(BaseModel):
    id: int
    sku: Optional[str]
    name: str
    qty: float
    unit_price: float
    line_total: float
    item_type: str

    class Config:
        from_attributes = True

class PaymentOut(BaseModel):
    id: int
    created_at: datetime
    amount: float
    method: str
    reference: Optional[str]
    notes: Optional[str]
    voided: bool

    class Config:
        from_attributes = True

class OrderOut(BaseModel):
    id: int
    code: str
    parent_order_id: Optional[int]
    created_at: datetime
    order_type: str
    event_type: str
    status: str
    customer_name: str
    phone: Optional[str]
    address: Optional[str]
    location_url: Optional[str]
    subtotal: float
    discount: float
    delivery_fee: float
    return_delivery_fee: float
    penalty_amount: float
    buyback_amount: float
    total: float
    paid_initial: float
    to_collect_initial: float
    rental_monthly_total: float
    rental_start_date: Optional[datetime]
    instalment_months_total: int
    instalment_monthly_amount: float
    instalment_start_date: Optional[datetime]
    notes: Optional[str]
    items: list[OrderItemOut]
    payments: list[PaymentOut]
    outstanding_estimate: float

    class Config:
        from_attributes = True

class PaymentCreate(BaseModel):
    amount: float
    method: str = "CASH"
    reference: Optional[str] = None
    notes: Optional[str] = None

class ManualOrderCreate(BaseModel):
    parsed: ParsedOrder



