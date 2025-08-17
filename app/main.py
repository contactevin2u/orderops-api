from fastapi import FastAPI, Response, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime, date
from io import BytesIO, StringIO
import os, re, csv, json

# ---- storage / models
try:
    from app.storage import (
        SessionLocal, init_db, Order, Payment, Event,
        OrderMeta, OrderItem, Charge,
        Delivery, AuditLog, IdempotencyKey, compute_rental_accrual
    )
except Exception:
    # Fallback if you kept earlier simpler storage
    from app.storage import (
        SessionLocal, init_db, Order, Payment, Event,
        OrderMeta, OrderItem, Charge
    )
    Delivery = AuditLog = IdempotencyKey = None
    def compute_rental_accrual(*args, **kwargs): return 0.0

# ---- optional OpenAI
openai_client = None
try:
    from openai import OpenAI
    if os.getenv("OPENAI_API_KEY"):
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    openai_client = None

# ---- XLSX
try:
    from openpyxl import Workbook
except Exception:
    Workbook = None

app = FastAPI(title="OrderOps API")

# ---- CORS
FRONTEND_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "").split(",") if o.strip()]
FRONTEND_REGEX = os.getenv("FRONTEND_ORIGIN_REGEX") or None
if not FRONTEND_ORIGINS and not FRONTEND_REGEX:
    FRONTEND_ORIGINS = ["http://localhost:3000"]  # safe default for local dev

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_origin_regex=FRONTEND_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Static files (safe guard)
_files_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "files"))
os.makedirs(_files_dir, exist_ok=True)
app.mount("/files", StaticFiles(directory=_files_dir), name="files")

# ---- Catalog (extend as needed)
CATALOG = [
    {"sku":"BED-2F","name":"Hospital Bed 2 Function","sale_price":2800.0,"rent_monthly":380.0,"buyback_rate":0.40},
    {"sku":"BED-3F","name":"Hospital Bed 3 Function","sale_price":3800.0,"rent_monthly":480.0,"buyback_rate":0.45},
    {"sku":"BED-5F","name":"Hospital Bed 5 Function","sale_price":5200.0,"rent_monthly":650.0,"buyback_rate":0.45},
    {"sku":"BED-3F-AUTO","name":"Hospital Bed 3F Auto","sale_price":6200.0,"rent_monthly":780.0,"buyback_rate":0.45},
    {"sku":"WHL-STEEL","name":"Auto Wheelchair (Steel)","sale_price":800.0,"rent_monthly":120.0,"buyback_rate":0.35},
    {"sku":"WHL-ALU","name":"Auto Wheelchair (Aluminium)","sale_price":1200.0,"rent_monthly":160.0,"buyback_rate":0.35},
    {"sku":"WHL-HD","name":"Heavy Duty Wheelchair","sale_price":1600.0,"rent_monthly":220.0,"buyback_rate":0.35},
    {"sku":"O2-5L","name":"Oxygen Concentrator 5L","sale_price":2800.0,"rent_monthly":420.0,"buyback_rate":0.40},
    {"sku":"O2-10L","name":"Oxygen Concentrator 10L","sale_price":4300.0,"rent_monthly":580.0,"buyback_rate":0.40},
    {"sku":"O2-TANK","name":"Oxygen Tank","sale_price":550.0,"rent_monthly":90.0,"buyback_rate":0.20},
    {"sku":"TLM-CAN","name":"Canvas Mattress","sale_price":199.0,"rent_monthly":0.0,"buyback_rate":0.10},
]

# ---- Schemas
class ItemIn(BaseModel):
    sku: str
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

class EventIn(BaseModel):
    event: Literal["RETURN","COLLECT","INSTALMENT_CANCEL","BUYBACK"]
    penalty: Optional[float] = None
    delivery_return_fee: Optional[float] = None
    buyback_rate: Optional[float] = None

class ParseIn(BaseModel):
    text: str
    matcher: Literal["ai","rapidfuzz","hybrid"] = "hybrid"
    lang: Literal["en","ms"] = "en"

# ---- util
def rental_monthly_total(items: List[OrderItem]) -> float:
    return sum((i.rent_monthly or 0) * i.qty for i in items)

def sum_charges(charges: List[Charge], kinds=None) -> float:
    if kinds is None: return sum(c.amount for c in charges)
    return sum(c.amount for c in charges if c.kind in kinds)

def sum_payments(pays: List[Payment]) -> float:
    return sum(p.amount for p in pays)

def compute_outstanding(meta, items, charges, pays, as_of: date) -> Dict[str, Any]:
    accrual = 0.0
    if meta and meta.type == "RENTAL" and meta.plan_start_date:
        start = meta.plan_start_date.date() if hasattr(meta.plan_start_date, "date") else meta.plan_start_date
        accrual = compute_rental_accrual(items, start, as_of)
    principal = sum_charges(charges, ["PRINCIPAL"])
    delivery = sum_charges(charges, ["DELIVERY_OUTBOUND","DELIVERY_RETURN"])
    penalty  = sum_charges(charges, ["PENALTY"])
    credits  = sum_charges(charges, ["BUYBACK_CREDIT","ADJUSTMENT"])
    paid     = sum_payments(pays)
    total_due = principal + delivery + penalty + accrual + credits
    outstanding = max(0.0, round(total_due - paid, 2))
    return {"principal":principal,"delivery":delivery,"penalty":penalty,"accrual":accrual,"other_credits":credits,"paid":paid,"total_due":total_due,"outstanding":outstanding}

# ---- lifecycle
@app.on_event("startup")
def _startup(): init_db()

# ---- endpoints (same surface as we agreed)
@app.get("/health")
def health(): return {"ok": True}

@app.get("/catalog")
def catalog(): return {"items": CATALOG}

@app.post("/orders")
def create_order(body: OrderCreate, idem_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    now = datetime.utcnow()
    with SessionLocal() as s:
        # idempotency (if table exists)
        if IdempotencyKey and idem_key:
            exists = s.query(IdempotencyKey).filter_by(key=idem_key, endpoint="/orders").first()
            if exists: raise HTTPException(409, detail="Duplicate request")
            s.add(IdempotencyKey(key=idem_key, endpoint="/orders", created_at=now))

        if s.get(Order, body.code):
            raise HTTPException(409, detail="Order code already exists")

        s.add(Order(code=body.code, created_at=now))
        s.add(OrderMeta(
            order_code=body.code, type=body.type, status="OPEN",
            customer_name=body.customer.name, phone=body.customer.phone, address=body.customer.address,
            plan_months=body.plan_months, plan_monthly_amount=body.plan_monthly_amount,
            plan_start_date=body.plan_start_date or now.date()
        ))
        for it in body.items:
            s.add(OrderItem(order_code=body.code, sku=it.sku, name=it.name, qty=it.qty,
                            unit_price=it.unit_price, rent_monthly=it.rent_monthly, buyback_rate=it.buyback_rate))

        # charges
        if body.type in ("OUTRIGHT","INSTALMENT"):
            principal = sum((it.unit_price or 0) * it.qty for it in body.items)
            if principal > 0:
                s.add(Charge(order_code=body.code, kind="PRINCIPAL", amount=principal, note="Items principal", created_at=now))
        if body.delivery.prepaid_outbound and body.delivery.outbound_fee:
            s.add(Charge(order_code=body.code, kind="DELIVERY_OUTBOUND", amount=body.delivery.outbound_fee, note="Prepaid outbound", created_at=now))
        if body.delivery.prepaid_return and body.delivery.return_fee:
            s.add(Charge(order_code=body.code, kind="DELIVERY_RETURN", amount=body.delivery.return_fee, note="Prepaid return", created_at=now))

        # schedule (if Delivery table exists)
        if Delivery and body.schedule and (body.schedule.date or body.schedule.time):
            s.add(Delivery(order_code=body.code,
                           outbound_date=datetime.combine(body.schedule.date or now.date(), datetime.min.time()),
                           outbound_time=body.schedule.time or None,
                           status="SCHEDULED"))

        if AuditLog:
            s.add(AuditLog(order_code=body.code, action="CREATE_ORDER", meta={"source":"api"}, created_at=now))
        s.commit()
    return {"ok": True, "code": body.code}

@app.get("/orders")
def list_orders(q: Optional[str] = None,
                type: Optional[str] = Query(default=None, pattern="^(OUTRIGHT|INSTALMENT|RENTAL)$"),
                status: Optional[str] = Query(default=None, pattern="^(OPEN|CLOSED)$"),
                page: int = 1, page_size: int = 20, as_of: Optional[date] = None):
    as_of = as_of or datetime.utcnow().date()
    with SessionLocal() as s:
        metas = s.query(OrderMeta).all()
        result = []
        for m in metas:
            if type and m.type != type: continue
            if status and m.status != status: continue
            hay = f"{m.order_code} {m.customer_name or ''} {m.phone or ''}".lower()
            if q and q.lower() not in hay: continue
            items = s.query(OrderItem).filter(OrderItem.order_code==m.order_code).all()
            charges = s.query(Charge).filter(Charge.order_code==m.order_code).all()
            pays = s.query(Payment).filter(Payment.order_code==m.order_code).all()
            summary = compute_outstanding(m, items, charges, pays, as_of)
            result.append({
                "code": m.order_code, "type": m.type, "status": m.status,
                "customer": {"name": m.customer_name, "phone": m.phone},
                "created_at": s.get(Order, m.order_code).created_at.isoformat(),
                "outstanding": summary["outstanding"]
            })
        total = len(result); start = (page-1)*page_size; end = start+page_size
        return {"page": page, "page_size": page_size, "total": total, "orders": result[start:end]}

@app.get("/orders/{code}")
def get_order(code: str, as_of: Optional[date] = None):
    as_of = as_of or datetime.utcnow().date()
    with SessionLocal() as s:
        order = s.get(Order, code)
        if not order: raise HTTPException(404, detail="Order not found")
        meta = s.get(OrderMeta, code)
        items = s.query(OrderItem).filter(OrderItem.order_code==code).all()
        charges = s.query(Charge).filter(Charge.order_code==code).all()
        pays = s.query(Payment).filter(Payment.order_code==code).all()
        events = s.query(Event).filter(Event.order_code==code).all()
        summary = compute_outstanding(meta, items, charges, pays, as_of)
        return {"order":{"code":code,"created_at":order.created_at.isoformat()},
                "meta": meta.__dict__ if meta else None,
                "items":[{k:getattr(i,k) for k in ("id","sku","name","qty","unit_price","rent_monthly","buyback_rate")} for i in items],
                "charges":[{k:getattr(c,k) for k in ("id","kind","amount","note","created_at")} for c in charges],
                "payments":[{k:getattr(p,k) for k in ("id","amount","created_at")} for p in pays],
                "events":[{k:getattr(e,k) for k in ("id","kind","created_at")} for e in events],
                "summary": summary}

@app.post("/orders/{code}/payments")
def payment(code: str, body: PaymentIn):
    now = datetime.utcnow()
    with SessionLocal() as s:
        if not s.get(Order, code): s.add(Order(code=code, created_at=now))
        p = Payment(order_code=code, amount=body.amount, created_at=now); s.add(p); s.commit()
        return {"ok": True, "payment_id": p.id, "code": code, "amount": body.amount}

@app.post("/orders/{code}/event")
def post_event(code: str, body: EventIn):
    now = datetime.utcnow()
    with SessionLocal() as s:
        if not s.get(Order, code): raise HTTPException(404, detail="Order not found")
        meta = s.get(OrderMeta, code)
        events = s.query(Event).filter(Event.order_code==code).all()
        if any(e.kind in ("RETURN","COLLECT","INSTALMENT_CANCEL","BUYBACK") for e in events):
            raise HTTPException(400, detail="Terminal event already recorded for this order")

        if body.event == "INSTALMENT_CANCEL":
            if body.penalty and body.penalty > 0:
                s.add(Charge(order_code=code, kind="PENALTY", amount=body.penalty, note="Instalment cancel penalty", created_at=now))
            if body.delivery_return_fee and body.delivery_return_fee > 0:
                s.add(Charge(order_code=code, kind="DELIVERY_RETURN", amount=body.delivery_return_fee, note="Return delivery (cancel)", created_at=now))
            if meta: meta.status="CLOSED"; meta.closed_at=now
        elif body.event == "BUYBACK":
            items = s.query(OrderItem).filter(OrderItem.order_code==code).all()
            credit = 0.0
            for it in items:
                if it.unit_price:
                    rate = (it.buyback_rate or body.buyback_rate or 0.5)
                    credit += it.unit_price * it.qty * max(0.0, min(1.0, rate))
            if credit != 0:
                s.add(Charge(order_code=code, kind="BUYBACK_CREDIT", amount=-abs(credit), note="Buyback credit", created_at=now))
            if meta: meta.status="CLOSED"; meta.closed_at=now
        elif body.event in ("RETURN","COLLECT"):
            if body.event=="RETURN" and body.delivery_return_fee and body.delivery_return_fee>0:
                s.add(Charge(order_code=code, kind="DELIVERY_RETURN", amount=body.delivery_return_fee, note="Return delivery", created_at=now))
            if meta: meta.status="CLOSED"; meta.closed_at=now

        s.add(Event(order_code=code, kind=body.event, created_at=now))
        s.commit()
        return {"ok": True, "code": code, "event": body.event}

@app.post("/parse")
def parse(body: ParseIn, idem_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    # Optional OpenAI client (present elsewhere in file)
    global openai_client
    result = parse_whatsapp(body.text, openai_client=openai_client if body.matcher == "ai" and openai_client is not None else None)
    # keep original response shape
    return result

from .storage import SessionLocal, OrderMeta, OrderItem, Charge, Payment, Event, Delivery, compute_rental_accrual
try:
    from .storage import SessionLocal, OrderMeta, OrderItem, Charge, Payment, Event, Delivery, compute_rental_accrual
except Exception:
    pass
@app.get("/calendar")
def calendar(from_date: date | None = None, to_date: date | None = None):
    with SessionLocal() as s:
        rows = s.query(Delivery).all()
        out = []
        for d in rows:
            if d.outbound_date:
                dt = d.outbound_date.date()
                if from_date and dt < from_date:
                    pass
                elif to_date and dt > to_date:
                    pass
                else:
                    out.append({
                        "order_code": d.order_code,
                        "date": dt.isoformat(),
                        "time": d.outbound_time,
                        "kind": "OUTBOUND",
                        "status": d.status
                    })
            if d.return_date:
                dt2 = d.return_date.date()
                if from_date and dt2 < from_date:
                    pass
                elif to_date and dt2 > to_date:
                    pass
                else:
                    out.append({
                        "order_code": d.order_code,
                        "date": dt2.isoformat(),
                        "time": d.return_time,
                        "kind": "RETURN",
                        "status": d.status
                    })
        return {"events": out}
@app.get("/reports/aging")
def report_aging(as_of: date | None = None):
    as_of = as_of or datetime.utcnow().date()
    buckets = {"0-30":0.0,"31-60":0.0,"61-90":0.0,"90+":0.0}
    rows = []
    with SessionLocal() as s:
        metas = s.query(OrderMeta).all()
        for m in metas:
            items = s.query(OrderItem).filter_by(order_code=m.order_code).all()
            charges = s.query(Charge).filter_by(order_code=m.order_code).all()
            pays = s.query(Payment).filter_by(order_code=m.order_code).all()

            principal = sum(c.amount for c in charges if c.kind == "PRINCIPAL")
            delivery  = sum(c.amount for c in charges if c.kind in ("DELIVERY_OUTBOUND","DELIVERY_RETURN"))
            penalty   = sum(c.amount for c in charges if c.kind == "PENALTY")
            credits   = sum(c.amount for c in charges if c.kind in ("BUYBACK_CREDIT","ADJUSTMENT"))
            accrual   = 0.0
            if m.type == "RENTAL" and m.plan_start_date:
                start_d = m.plan_start_date.date() if hasattr(m.plan_start_date, "date") else m.plan_start_date
                accrual = compute_rental_accrual(items, start_d, as_of)
            paid      = sum(p.amount for p in pays)
            total_due = principal + delivery + penalty + accrual + credits
            outstanding = round(max(0.0, total_due - paid), 2)

            if outstanding <= 0:
                continue
            start_for_age = m.plan_start_date.date() if (m.plan_start_date and hasattr(m.plan_start_date,"date")) else (m.plan_start_date or as_of)
            age_days = (as_of - start_for_age).days if start_for_age else 0
            if   age_days <= 30: bucket = "0-30"
            elif age_days <= 60: bucket = "31-60"
            elif age_days <= 90: bucket = "61-90"
            else:                bucket = "90+"
            buckets[bucket] += outstanding
            rows.append({"code": m.order_code, "customer": m.customer_name, "type": m.type, "age_days": age_days, "outstanding": outstanding})
    return {"as_of": as_of.isoformat(), "buckets": buckets, "rows": rows}
