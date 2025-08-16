from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

_ALLOWED_TYPES = {"RENTAL", "INSTALMENT", "OUTRIGHT"}
_ALLOWED_EVENT_TYPES = {"NONE", "RETURN", "COLLECT", "INSTALMENT_CANCEL", "BUYBACK"}

class ItemIn(BaseModel):
    sku: Optional[str] = None
    name: str
    qty: int = 1
    unit_price: float = 0.0

class PlanIn(BaseModel):
    cadence: str = "MONTHLY"
    term_months: Optional[int] = None
    monthly_amount: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    @field_validator("cadence")
    @classmethod
    def _norm_cadence(cls, v):
        v = (v or "MONTHLY").upper()
        if v != "MONTHLY":
            raise ValueError("cadence must be MONTHLY")
        return v

class OrderIn(BaseModel):
    order_id: Optional[str] = None
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    type: str
    due_date: Optional[str] = None
    return_due_date: Optional[str] = None
    created_at: Optional[str] = None
    items: List[ItemIn] = Field(default_factory=list)
    notes: Optional[str] = None
    plan: Optional[PlanIn] = None

    @field_validator("type")
    @classmethod
    def _norm_type(cls, v):
        v = (v or "").upper()
        if v not in _ALLOWED_TYPES:
            raise ValueError(f"type must be one of {sorted(_ALLOWED_TYPES)}")
        return v

class EventIn(BaseModel):
    type: Optional[str] = "NONE"
    reference_order_id: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    delivery_fee: Optional[float] = None
    penalty_amount: Optional[float] = None
    buyback_amount: Optional[float] = None
    auto_discount: Optional[bool] = True
    created_at: Optional[str] = None

    @field_validator("type")
    @classmethod
    def _norm_event_type(cls, v):
        v = (v or "NONE").upper()
        if v not in _ALLOWED_EVENT_TYPES:
            v = "NONE"
        return v

class IntakePayload(BaseModel):
    order: OrderIn
    event: Optional[EventIn] = None
