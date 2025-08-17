from fastapi import FastAPI, Response, HTTPException, Query, Header
import app.audit_hooks  # register SQLAlchemy event listeners
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime, date
from io import BytesIO
import os, json

from app.db import SessionLocal
from app.models import (
    Order, OrderItem, Payment, Event, Customer, PaymentPlan, LedgerEntry,
    Delivery, AuditLog, IdempotencyKey
)

# Optional OpenAI client (tolerant)
openai_client = None
try:
    from openai import OpenAI
    if os.getenv("OPENAI_API_KEY"):
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    openai_client = None

# XLSX
try:
    from openpyxl import Workbook
except Exception:
    Workbook = None

app = FastAPI(title="OrderOps API")

# ---- CORS
FRONTEND_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "").split(",") if o.strip()]
FRONTEND_REGEX = os.getenv("FRONTEND_ORIGIN_REGEX") or None
if not FRONTEND_ORIGINS and not FRONTEND_REGEX:
    FRONTEND_ORIGINS = ["http://localhost:3000"]  # local dev default

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_origin_regex=FRONTEND_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Static files
_files_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "files"))
os.makedirs(_files_dir, exist_ok=True)
app.mount("/files", StaticFiles(directory=_files_dir), name="files")

# Catalog (sample)
CATALOG = [
    {"sku":"BED-2F","name":"Hospital Bed 2F","sale_price":2800.0,"rent_monthly":380.0,"buyback_rate":0.40},
    {"sku":"BED-3F","name":"Hospital Bed 3F","sale_price":3800.0,"rent_monthly":480.0,"buyback_rate":0.45},
    {"sku":"O2-5L","name":"Oxygen Concentrator 5L","sale_price":2800.0,"rent_monthly":420.0,"buyback_rate":0.40},
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

# ---- Helpers
def months_between(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))

def compute_accrual(order: Order, as_of: date) -> float:
    try:
        if order.type != "RENTAL":
            return 0.0
        plan = order.plan
        if not plan or not plan.start_date or not plan.monthly_amount:
            return 0.0
        months = months_between(plan.start_date, as_of)
        return round(float(plan.monthly_amount or 0) * months, 2)
    except Exception:
        return 0.0

def compute_outstanding(order: Order, as_of: date) -> Dict[str, Any]:
    accrual = compute_accrual(order, as_of)
    ledger_sum = sum(float(getattr(le, "amount", 0) or 0) for le in (order.ledger or []))
    paid = sum(float(getattr(p, "amount", 0) or 0) for p in (order.payments or []))
    total_due = ledger_sum + accrual
    outstanding = max(0.0, round(total_due - paid, 2))
    return {"accrual": accrual, "ledger": ledger_sum, "paid": paid, "total_due": total_due, "outstanding": outstanding}

# ---- Optional metrics router (won't crash if missing)
try:
    from app.metrics import router as metrics_router
    app.include_router(metrics_router)
except Exception:
    pass

@app.get("/health")
def health(): 
    return {"ok": True}

@app.get("/catalog")
def catalog(): 
    return {"items": CATALOG}

@app.post("/orders")
def create_order(body: OrderCreate, idem_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    now = datetime.utcnow()
    with SessionLocal() as s:
        if idem_key:
            exists = s.query(IdempotencyKey).filter_by(key=idem_key, path="/orders").first()
            if exists:
                raise HTTPException(409, detail="Duplicate request")
            s.add(IdempotencyKey(key=idem_key, method="POST", path="/orders", status_code=202, created_at=now))

        if s.query(Order).filter_by(order_code=body.code).first():
            raise HTTPException(409, detail="Order code already exists")

        # customer upsert by phone
        cust = None
        if body.customer.phone:
            cust = s.query(Customer).filter_by(phone=body.customer.phone).first()
        if not cust:
            cust = Customer(name=body.customer.name, phone=body.customer.phone, address=body.customer.address)
            s.add(cust); s.flush()

        order = Order(order_code=body.code, customer=cust, type=body.type, status="CONFIRMED", created_at=now)
        s.add(order); s.flush()

        for it in body.items:
            s.add(OrderItem(order_id=order.id, order_code=order.code, sku=it.sku, name=it.name, qty=it.qty, unit_price=(it.unit_price or 0)))

        if body.type in ("OUTRIGHT","INSTALMENT"):
            principal = sum((it.unit_price or 0) * it.qty for it in body.items)
            if principal > 0:
                s.add(LedgerEntry(order_id=order.id, order_code=order.code, kind="INITIAL_CHARGE", amount=principal, note="Items principal"))

        if body.type == "RENTAL" or (body.plan_monthly_amount or body.plan_months or body.plan_start_date):
            s.add(PaymentPlan(
                order_id=order.id, order_code=order.code, cadence="MONTHLY",
                term_months=body.plan_months,
                monthly_amount=body.plan_monthly_amount or sum((it.rent_monthly or 0) * it.qty for it in body.items),
                start_date=body.plan_start_date or now.date()
            ))

        if body.delivery and body.delivery.prepaid_outbound and body.delivery.outbound_fee:
            s.add(LedgerEntry(order_id=order.id, order_code=order.code, kind="ADJUSTMENT", amount=body.delivery.outbound_fee, note="Prepaid outbound delivery"))
        if body.delivery and body.delivery.prepaid_return and body.delivery.return_fee:
            s.add(LedgerEntry(order_id=order.id, order_code=order.code, kind="ADJUSTMENT", amount=body.delivery.return_fee, note="Prepaid return delivery"))

        if body.schedule and (body.schedule.date or body.schedule.time):
            s.add(Delivery(order_id=order.id, order_code=order.code, outbound_date=body.schedule.date or now.date(), outbound_time=body.schedule.time, status="SCHEDULED"))

        s.add(AuditLog(order_id=order.id, order_code=order.code, action="CREATE_ORDER", meta=json.dumps({"source":"api"})))
        s.commit()
        return {"ok": True, "code": body.code}

@app.get("/orders")
def list_orders(q: Optional[str] = None,
                type: Optional[str] = Query(default=None, pattern="^(OUTRIGHT|INSTALMENT|RENTAL)$"),
                status: Optional[str] = Query(default=None, pattern="^(CONFIRMED|RETURNED|CANCELLED)$"),
                page: int = 1, page_size: int = 20, as_of: Optional[date] = None):
    as_of = as_of or datetime.utcnow().date()
    with SessionLocal() as s:
        orders = s.query(Order).all()
        out = []
        for o in orders:
            if type and (o.type != type): continue
            if status and (o.status != status): continue
            hay = f"{o.order_code} {(o.customer.name if o.customer else '')} {(o.customer.phone if o.customer else '')}".lower()
            if q and q.lower() not in hay: continue
            summary = compute_outstanding(o, as_of)
            out.append({
                "code": o.order_code,
                "type": o.type,
                "status": o.status,
                "customer": {"name": o.customer.name if o.customer else None, "phone": o.customer.phone if o.customer else None},
                "created_at": (o.created_at.isoformat() if o.created_at else None),
                "outstanding": summary["outstanding"]
            })
        total = len(out); start = (page-1)*page_size; end = start+page_size
        return {"page": page, "page_size": page_size, "total": total, "orders": out[start:end]}

@app.get("/orders/{code}")
def get_order(code: str, as_of: Optional[date] = None):
    as_of = as_of or datetime.utcnow().date()
    with SessionLocal() as s:
        order = s.query(Order).filter_by(order_code=code).first()
        if not order:
            raise HTTPException(404, detail="Order not found")
        summary = compute_outstanding(order, as_of)
        return {
            "order":{"code":order.order_code,"created_at":order.created_at.isoformat() if order.created_at else None},
            "meta": {"type": order.type, "status": order.status,
                     "customer_name": (order.customer.name if order.customer else None),
                     "phone": (order.customer.phone if order.customer else None)},
            "items":[{"id":i.id,"sku":i.sku,"name":i.name,"qty":i.qty,"unit_price":float(i.unit_price or 0)} for i in (order.items or [])],
            "payments":[{"id":p.id,"amount":float(p.amount or 0),"created_at":p.created_at.isoformat()} for p in (order.payments or [])],
            "events":[{"id":e.id,"kind":e.type,"created_at":e.created_at.isoformat()} for e in (order.events or [])],
            "summary": summary
        }

@app.post("/orders/{code}/payments")
def payment(code: str, body: PaymentIn):
    now = datetime.utcnow()
    with SessionLocal() as s:
        order = s.query(Order).filter_by(order_code=code).first()
        if not order:
            raise HTTPException(404, detail="Order not found")
        p = Payment(order_id=order.id, order_code=order.code, amount=body.amount, method=(body.method or "CASH"), created_at=now)
        s.add(p); s.commit()
        return {"ok": True, "payment_id": p.id, "code": code, "amount": body.amount}

@app.post("/orders/{code}/event")
def post_event(code: str, body: EventIn):
    now = datetime.utcnow()
    with SessionLocal() as s:
        order = s.query(Order).filter_by(order_code=code).first()
        if not order:
            raise HTTPException(404, detail="Order not found")
        if any((e.type in ("RETURN","COLLECT","INSTALMENT_CANCEL","BUYBACK")) for e in (order.events or [])):
            raise HTTPException(400, detail="Terminal event already recorded for this order")
        if body.event == "INSTALMENT_CANCEL":
            if body.penalty and body.penalty > 0:
                s.add(LedgerEntry(order_id=order.id, order_code=order.code, kind="ADJUSTMENT", amount=body.penalty, note="Instalment cancel penalty"))
            if body.delivery_return_fee and body.delivery_return_fee > 0:
                s.add(LedgerEntry(order_id=order.id, order_code=order.code, kind="ADJUSTMENT", amount=body.delivery_return_fee, note="Return delivery (cancel)"))
            order.status = "CANCELLED"
        elif body.event == "BUYBACK":
            rate = max(0.0, min(1.0, body.buyback_rate or 0.5))
            credit = 0.0
            for it in (order.items or []):
                if it.unit_price:
                    credit += float(it.unit_price) * it.qty * rate
            if credit != 0:
                s.add(LedgerEntry(order_id=order.id, order_code=order.code, kind="ADJUSTMENT", amount=-abs(credit), note="Buyback credit"))
            order.status = "RETURNED"
        elif body.event in ("RETURN","COLLECT"):
            if body.event=="RETURN" and body.delivery_return_fee and body.delivery_return_fee>0:
                s.add(LedgerEntry(order_id=order.id, order_code=order.code, kind="ADJUSTMENT", amount=body.delivery_return_fee, note="Return delivery"))
            order.status = "RETURNED"
        s.add(Event(order_id=order.id, order_code=order.code, type=body.event, created_at=now))
        s.add(AuditLog(order_id=order.id, order_code=order.code, action=("EVENT_"+body.event), meta=json.dumps({"source":"api"})))
        s.commit()
        return {"ok": True, "code": code, "event": body.event}

@app.post("/parse")
def parse(body: ParseIn, idem_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    try:
        from app.parser_spacy import parse_whatsapp
        res = parse_whatsapp(body.text, openai_client=openai_client if (body.matcher=="ai" and openai_client) else None)
        return res
    except Exception:
        return {"ok": False, "detail": "Parser not available", "text": body.text}

@app.get("/calendar")
def calendar(from_date: date | None = None, to_date: date | None = None):
    with SessionLocal() as s:
        rows = s.query(Delivery).all()
        out = []
        for d in rows:
            code = None
            if d.order_id:
                o = s.query(Order).get(d.order_id)
                code = o.order_code if o else None
            if d.outbound_date:
                dt = d.outbound_date
                if (from_date and dt < from_date) or (to_date and dt > to_date): pass
                else: out.append({"order_code": code, "date": dt.isoformat(), "time": d.outbound_time, "kind": "OUTBOUND", "status": d.status})
            if d.return_date:
                dt2 = d.return_date
                if (from_date and dt2 < from_date) or (to_date and dt2 > to_date): pass
                else: out.append({"order_code": code, "date": dt2.isoformat(), "time": d.return_time, "kind": "RETURN", "status": d.status})
        return {"events": out}

@app.get("/reports/aging")
def report_aging(as_of: date | None = None):
    as_of = as_of or datetime.utcnow().date()
    buckets = {"0-30":0.0,"31-60":0.0,"61-90":0.0,"90+":0.0}
    rows = []
    with SessionLocal() as s:
        for o in s.query(Order).all():
            summary = compute_outstanding(o, as_of)
            outstanding = summary["outstanding"]
            if outstanding <= 0: continue
            start_for_age = (o.plan.start_date if (o.plan and o.plan.start_date) else (o.created_at.date() if o.created_at else as_of))
            age_days = (as_of - start_for_age).days if start_for_age else 0
            bucket = "0-30" if age_days<=30 else ("31-60" if age_days<=60 else ("61-90" if age_days<=90 else "90+"))
            buckets[bucket] += outstanding
            rows.append({"code": o.order_code, "customer": (o.customer.name if o.customer else None), "type": o.type, "age_days": age_days, "outstanding": outstanding})
    return {"as_of": as_of.isoformat(), "buckets": buckets, "rows": rows}

@app.get("/export/xlsx")
def export_xlsx():
    if Workbook is None:
        raise HTTPException(501, detail="openpyxl not installed")
    wb = Workbook()
    ws = wb.active
    ws.title = "Orders"
    ws.append(["Code","Customer","Type","CreatedAt","Outstanding"])
    with SessionLocal() as s:
        today = datetime.utcnow().date()
        for o in s.query(Order).all():
            summary = compute_outstanding(o, today)
            ws.append([
                o.order_code,
                (o.customer.name if o.customer else ""),
                o.type,
                (o.created_at.isoformat() if o.created_at else ""),
                summary["outstanding"],
            ])
    buf = BytesIO()
    wb.save(buf); buf.seek(0)
    return Response(content=buf.read(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition":"attachment; filename=orders.xlsx"})