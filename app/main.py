from __future__ import annotations
from fastapi import FastAPI, Depends, HTTPException, Body, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from datetime import date
from decimal import Decimal
import os, sentry_sdk

from .settings import settings
from .db import Base, engine, get_db
from .models import (
    Order, OrderItem, Customer, Event, Payment,
    OrderType, OrderStatus, EventType,
    PaymentPlan, IdempotencyKey,
    LedgerEntry, LedgerKind, CodeReservation, Job
)
from .schemas import IntakePayload, EventIn
from .parsing import parse_message
from .codes import next_code
from .pdfs import invoice_pdf_bytes, receipt_pdf_bytes
from .excel_export import build_export_csv
from .util import norm_phone
from .match import match_order
from .metrics import router as metrics_router, PARSE_LATENCY, MATCH_HIT, ACCRUAL_CREATED
from .idempotency import IdempotencyMiddleware
from .storage import store_bytes

if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.2)

app = FastAPI(default_response_class=ORJSONResponse)
app.add_middleware(GZipMiddleware)
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CORS_ORIGIN] if settings.CORS_ORIGIN != "*" else ["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
Base.metadata.create_all(bind=engine)
app.include_router(metrics_router)

# Static files for local storage
files_dir = os.path.join(os.path.dirname(__file__), "..", "files")
app.mount("/files", StaticFiles(directory=files_dir), name="files")

def _to_date(s: str | None):
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except Exception:
        return None

def _order_charges(o: Order):
    initial = sum(float(l.amount) for l in o.ledger if l.kind == LedgerKind.INITIAL_CHARGE)
    monthly = sum(float(l.amount) for l in o.ledger if l.kind == LedgerKind.MONTHLY_CHARGE)
    paid = sum(float(p.amount) for p in o.payments)
    outstanding = initial + monthly - paid
    return initial, monthly, paid, outstanding

def _infer_recurring_deduction(o: Order) -> float:
    if not o.plan or not o.plan.monthly_amount:
        return 0.0
    monthly = float(o.plan.monthly_amount or 0)
    keywords = ("sewa", "rental", "bulan", "monthly", "instalmen", "ansuran")
    ded = 0.0
    for it in o.items:
        price = float(it.unit_price or 0)
        name = (it.name or "").lower()
        if abs(price - monthly) < 0.01 or any(k in name for k in keywords):
            ded += (it.qty or 1) * price
    return ded

def _ensure_initial_ledger(db: Session, order: Order):
    if any(l.kind == LedgerKind.INITIAL_CHARGE for l in order.ledger):
        return
    gross = sum((it.qty or 1) * float(it.unit_price or 0) for it in order.items)
    ded = _infer_recurring_deduction(order)
    total = max(gross - ded, 0.0)
    entry = LedgerEntry(order_id=order.id, kind=LedgerKind.INITIAL_CHARGE, amount=Decimal(str(total)), period=None, note="Initial from items")
    db.add(entry)
    db.flush()

def _months_between(start: date, end: date):
    cur = date(start.year, start.month, 1)
    last = date(end.year, end.month, 1)
    periods = []
    while cur <= last:
        periods.append(f"{cur.year:04d}-{cur.month:02d}")
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return periods

def _accrue_for_order(db: Session, order: Order, asof: date | None = None) -> int:
    if not order.plan or not order.plan.monthly_amount or not order.plan.active:
        return 0
    if not order.plan.start_date:
        order.plan.start_date = date.today()
    asof = asof or date.today()
    until = min(asof, order.plan.end_date) if order.plan.end_date else asof
    per_month = float(order.plan.monthly_amount or 0)
    existing_periods = {l.period for l in order.ledger if l.kind == LedgerKind.MONTHLY_CHARGE and l.period}
    new_count = 0
    for period in _months_between(order.plan.start_date, until):
        if period in existing_periods:
            continue
        entry = LedgerEntry(order_id=order.id, kind=LedgerKind.MONTHLY_CHARGE, amount=Decimal(str(per_month)), period=period, note=f"Monthly {period}")
        db.add(entry)
        new_count += 1
    if new_count:
        db.flush()
    ACCRUAL_CREATED.inc(new_count)
    return new_count

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/parse")
def parse_endpoint(raw: str = Body(..., embed=True), fast: bool = Body(default=True), lenient: bool = Body(default=True), matcher: str = Body(default="hybrid"), db: Session = Depends(get_db)):
    with PARSE_LATENCY.time():
        data = parse_message(raw, fast=fast, lenient=lenient)
    order_data = (data or {}).get("order", {}) or {}
    match = match_order(db, order_data.get("name"), order_data.get("phone"), order_data.get("order_id"), matcher=matcher)
    if match:
        MATCH_HIT.labels(match.get("reason") or "unknown").inc()
    return {"parsed": data, "match": match}

@app.get("/orders")
def list_orders(search: str | None = Query(default=None), db: Session = Depends(get_db)):
    query = db.query(Order)
    if search:
        like = f"%{search.strip()}%"
        query = query.join(Customer).filter(or_(Order.order_code.ilike(like), Customer.name.ilike(like), Customer.phone.ilike(like)))
    orders = query.options(joinedload(Order.customer)).order_by(Order.id.desc()).limit(50).all()
    results = []
    for o in orders:
        initial, monthly, paid, outstanding = _order_charges(o)
        results.append({
            "order_code": o.order_code,
            "external_id": o.external_id,
            "name": o.customer.name if o.customer else "",
            "phone": o.customer.phone if o.customer else "",
            "type": o.type.name if hasattr(o.type, "name") else str(o.type),
            "status": o.status.name if hasattr(o.status, "name") else str(o.status),
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "due_date": o.due_date.isoformat() if o.due_date else None,
            "outstanding": outstanding
        })
    return {"orders": results}

@app.get("/orders/{code}")
def get_order(code: str, db: Session = Depends(get_db)):
    o = db.query(Order).options(joinedload(Order.customer), joinedload(Order.items), joinedload(Order.events), joinedload(Order.payments), joinedload(Order.plan), joinedload(Order.ledger)).filter(Order.order_code == code).first()
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    initial, monthly, paid, outstanding = _order_charges(o)
    return {
        "order": {
            "order_code": o.order_code,
            "external_id": o.external_id,
            "name": o.customer.name if o.customer else "",
            "phone": o.customer.phone if o.customer else "",
            "address": o.customer.address if o.customer else "",
            "type": o.type.name if hasattr(o.type, "name") else str(o.type),
            "status": o.status.name if hasattr(o.status, "name") else str(o.status),
            "notes": o.notes,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "due_date": o.due_date.isoformat() if o.due_date else None,
            "return_due_date": o.return_due_date.isoformat() if o.return_due_date else None,
            "returned_at": o.returned_at.isoformat() if o.returned_at else None,
            "collected_at": o.collected_at.isoformat() if o.collected_at else None,
        },
        "customer": {
            "id": o.customer.id if o.customer else None,
            "name": o.customer.name if o.customer else "",
            "phone": o.customer.phone if o.customer else "",
            "address": o.customer.address if o.customer else ""
        },
        "items": [{"sku": it.sku, "name": it.name, "qty": it.qty, "unit_price": float(it.unit_price)} for it in o.items],
        "payments": [{"id": p.id, "amount": float(p.amount), "method": p.method, "created_at": p.created_at.isoformat()} for p in o.payments],
        "events": [{"id": e.id, "type": e.type.name if hasattr(e.type, "name") else str(e.type), "reason": e.reason, "notes": e.notes, "created_at": e.created_at.isoformat()} for e in o.events],
        "ledger": [{"id": l.id, "kind": l.kind.name if hasattr(l.kind, "name") else str(l.kind), "amount": float(l.amount), "period": l.period, "note": l.note, "entry_date": l.entry_date.isoformat()} for l in o.ledger],
        "charges": {"initial": initial, "monthly": monthly, "paid": paid, "outstanding": outstanding}
    }

@app.post("/orders")
def create_order(payload: IntakePayload, db: Session = Depends(get_db)):
    order_in = payload.order
    event_in = payload.event

    customer = None
    if order_in.phone:
        phone_norm = norm_phone(order_in.phone)
        customer = db.query(Customer).filter(Customer.phone_norm == phone_norm).first()
        if not customer:
            customer = Customer(name=order_in.name, phone=order_in.phone, phone_norm=phone_norm, address=order_in.address)
            db.add(customer)
            db.flush()

    new_order = Order(
        order_code=next_code(db),
        external_id=order_in.order_id,
        customer_id=customer.id if customer else None,
        type=OrderType[order_in.type],
        status=OrderStatus.CONFIRMED,
        notes=order_in.notes,
        due_date=_to_date(order_in.due_date),
        return_due_date=_to_date(order_in.return_due_date)
    )
    db.add(new_order)
    db.flush()

    if order_in.plan:
        plan_data = order_in.plan
        plan = PaymentPlan(
            order_id=new_order.id,
            cadence=plan_data.cadence or "MONTHLY",
            term_months=plan_data.term_months,
            monthly_amount=Decimal(str(plan_data.monthly_amount)) if plan_data.monthly_amount is not None else None,
            start_date=_to_date(plan_data.start_date),
            end_date=_to_date(plan_data.end_date),
            active=True
        )
        new_order.plan = plan

    for item in order_in.items:
        it = OrderItem(order_id=new_order.id, sku=item.sku, name=item.name, qty=item.qty, unit_price=Decimal(str(item.unit_price or 0)))
        new_order.items.append(it)

    db.flush()
    _ensure_initial_ledger(db, new_order)

    if event_in and event_in.type and event_in.type != "NONE":
        ev = Event(order_id=new_order.id, type=EventType[event_in.type], reason=event_in.reason, notes=event_in.notes)
        db.add(ev)
        if event_in.type in ["RETURN", "COLLECT"]:
            new_order.status = OrderStatus.RETURNED
            if event_in.delivery_fee:
                db.add(LedgerEntry(order_id=new_order.id, kind=LedgerKind.ADJUSTMENT, amount=Decimal(str(event_in.delivery_fee)), note="Delivery fee"))
            if event_in.penalty_amount:
                db.add(LedgerEntry(order_id=new_order.id, kind=LedgerKind.ADJUSTMENT, amount=Decimal(str(event_in.penalty_amount)), note="Penalty"))
        elif event_in.type == "INSTALMENT_CANCEL":
            new_order.status = OrderStatus.CANCELLED
            if new_order.plan:
                new_order.plan.active = False
            if event_in.penalty_amount:
                db.add(LedgerEntry(order_id=new_order.id, kind=LedgerKind.ADJUSTMENT, amount=Decimal(str(event_in.penalty_amount)), note="Penalty"))
        elif event_in.type == "BUYBACK":
            new_order.status = OrderStatus.CANCELLED
            if event_in.buyback_amount:
                db.add(LedgerEntry(order_id=new_order.id, kind=LedgerKind.ADJUSTMENT, amount=-Decimal(str(event_in.buyback_amount)), note="Buyback refund"))

    db.commit()
    return {"order_code": new_order.order_code}

@app.post("/orders/{code}/event")
def order_event(code: str, event: EventIn, db: Session = Depends(get_db)):
    o = db.query(Order).options(joinedload(Order.plan)).filter(Order.order_code == code).first()
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")

    ev = Event(order_id=o.id, type=EventType[event.type] if event.type else EventType.NONE, reason=event.reason, notes=event.notes)
    db.add(ev)

    etype = (event.type or "NONE").upper()
    if etype in ["RETURN", "COLLECT"]:
        o.status = OrderStatus.RETURNED
        if event.delivery_fee:
            db.add(LedgerEntry(order_id=o.id, kind=LedgerKind.ADJUSTMENT, amount=Decimal(str(event.delivery_fee)), note="Delivery fee"))
        if event.penalty_amount:
            db.add(LedgerEntry(order_id=o.id, kind=LedgerKind.ADJUSTMENT, amount=Decimal(str(event.penalty_amount)), note="Penalty"))
        if o.plan:
            o.plan.active = False
    elif etype == "INSTALMENT_CANCEL":
        o.status = OrderStatus.CANCELLED
        if o.plan:
            o.plan.active = False
        if event.penalty_amount:
            db.add(LedgerEntry(order_id=o.id, kind=LedgerKind.ADJUSTMENT, amount=Decimal(str(event.penalty_amount)), note="Penalty"))
    elif etype == "BUYBACK":
        o.status = OrderStatus.CANCELLED
        if event.buyback_amount:
            db.add(LedgerEntry(order_id=o.id, kind=LedgerKind.ADJUSTMENT, amount=-Decimal(str(event.buyback_amount)), note="Buyback refund"))

    db.commit()
    return {"message": f"Event '{event.type}' recorded for order {code}"}

@app.post("/orders/{code}/payments")
def add_payment(code: str, amount: float = Body(...), method: str = Body(default="CASH"), db: Session = Depends(get_db)):
    o = db.query(Order).filter(Order.order_code == code).first()
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    payment = Payment(order_id=o.id, amount=Decimal(str(amount)), method=method)
    db.add(payment)
    db.commit()
    return {"id": payment.id, "order_id": o.id, "amount": float(payment.amount), "method": payment.method, "created_at": payment.created_at.isoformat()}

@app.post("/orders/{code}/accrue")
def accrue_now(code: str, db: Session = Depends(get_db)):
    o = db.query(Order).filter(Order.order_code == code).first()
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    new_entries = _accrue_for_order(db, o)
    db.commit()
    return {"accrued_entries": new_entries}

@app.get("/orders/{code}/invoice.pdf")
def invoice_pdf(code: str, db: Session = Depends(get_db)):
    o = db.query(Order).options(joinedload(Order.customer), joinedload(Order.items)).filter(Order.order_code == code).first()
    if not o:
        raise HTTPException(status_code=404, detail="Not found")
    pdf_data = invoice_pdf_bytes(o)
    url = store_bytes("pdf", pdf_data, f"{code}.invoice.pdf")
    return {"url": url}

@app.get("/orders/{code}/receipt.pdf")
def receipt_pdf(code: str, amount: float, db: Session = Depends(get_db)):
    o = db.query(Order).options(joinedload(Order.customer)).filter(Order.order_code == code).first()
    if not o:
        raise HTTPException(status_code=404, detail="Not found")
    pdf_data = receipt_pdf_bytes(o, amount)
    url = store_bytes("pdf", pdf_data, f"{code}.receipt.{amount:.2f}.pdf")
    return {"url": url}

@app.get("/export/csv")
def export_csv(start: str | None = Query(default=None), end: str | None = Query(default=None),
               include_children: bool = Query(default=True), include_adjustments: bool = Query(default=True),
               only_unsettled: bool = Query(default=False), db: Session = Depends(get_db)):
    csv_data = build_export_csv(db, start=start, end=end, include_children=include_children, include_adjustments=include_adjustments, only_unsettled=only_unsettled)
    headers = {"Content-Disposition": f'attachment; filename="orders_{start or "all"}_{end or "all"}.csv"'}
    return Response(content=csv_data, media_type="text/csv", headers=headers)

