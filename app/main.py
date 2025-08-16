from __future__ import annotations
 
    $imports = $args[0].Groups[1].Value
    if ($imports -notmatch '\bHeader\b') { "from fastapi import $imports, Header" } else { $args[0].Value }
  
from fastapi.staticfiles import StaticFiles
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
from .storage import SessionLocal, init_db, Order, Payment, Event, OrderMeta, OrderItem, Charge, Delivery, AuditLog, IdempotencyKey, compute_rental_accrual

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
# (patched) removed static mount, name="files")

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
def create_order(body: OrderCreate, idem_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    now = datetime.utcnow()
    with SessionLocal() as s:
        if idem_key:
            exists = s.query(IdempotencyKey).filter_by(key=idem_key, endpoint="/orders").first()
            if exists:
                raise HTTPException(409, detail="Duplicate request (Idempotency-Key)")
            s.add(IdempotencyKey(key=idem_key, endpoint="/orders", created_at=now))

        if s.get(Order, body.code):
            raise HTTPException(409, detail="Order code already exists")

        s.add(Order(code=body.code, created_at=now))
        plan_months = body.plan_months or (body.plan.months if body.plan else None)
        plan_start  = body.plan_start_date or (body.plan.start_date if (body.plan and body.plan.start_date) else now.date())

        s.add(OrderMeta(
            order_code=body.code, type=body.type, status="OPEN",
            customer_name=body.customer.name, phone=body.customer.phone, address=body.customer.address,
            plan_months=plan_months, plan_monthly_amount=body.plan_monthly_amount,
            plan_start_date=plan_start
        ))

        for it in body.items:
            s.add(OrderItem(order_code=body.code, sku=it.sku, name=it.name, qty=it.qty,
                            unit_price=it.unit_price, rent_monthly=it.rent_monthly, buyback_rate=it.buyback_rate))

        # initial charges
        if body.type in ("OUTRIGHT","INSTALMENT"):
            principal = sum((it.unit_price or 0)*it.qty for it in body.items)
            if principal > 0:
                s.add(Charge(order_code=body.code, kind="PRINCIPAL", amount=principal, note="Items principal", created_at=now))

        if body.delivery.prepaid_outbound and body.delivery.outbound_fee:
            s.add(Charge(order_code=body.code, kind="DELIVERY_OUTBOUND", amount=body.delivery.outbound_fee, note="Prepaid outbound", created_at=now))
        if body.delivery.prepaid_return and body.delivery.return_fee:
            s.add(Charge(order_code=body.code, kind="DELIVERY_RETURN", amount=body.delivery_return_fee if hasattr(body, "delivery_return_fee") else body.delivery.return_fee, note="Prepaid return", created_at=now))

        # schedule
        if body.schedule and (body.schedule.date or body.schedule.time):
            s.add(Delivery(order_code=body.code,
                           outbound_date=datetime.combine(body.schedule.date or now.date(), datetime.min.time()),
                           outbound_time=body.schedule.time or None,
                           status="SCHEDULED"))

        s.add(AuditLog(order_code=body.code, action="CREATE_ORDER", meta={"payload":"created via API"}, created_at=now))
        s.commit()
    return {"ok": True, "code": body.code}@app.post("/orders/{code}/event")
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

@app.get("/calendar")
def calendar(from_date: Optional[date] = None, to_date: Optional[date] = None):
    with SessionLocal() as s:
        rows = s.query(Delivery).all()
        out = []
        for d in rows:
            if d.outbound_date:
                dt = d.outbound_date.date()
                if from_date and dt < from_date: continue
                if to_date and dt > to_date: continue
                out.append({"order_code": d.order_code, "date": dt.isoformat(), "time": d.outbound_time, "kind": "OUTBOUND", "status": d.status})
            if d.return_date:
                dt2 = d.return_date.date()
                if from_date and dt2 < from_date: continue
                if to_date and dt2 > to_date: continue
                out.append({"order_code": d.order_code, "date": dt2.isoformat(), "time": d.return_time, "kind": "RETURN", "status": d.status})
        return {"events": out}@app.get("/reports/aging")
def report_aging(as_of: Optional[date] = None):
    as_of = as_of or datetime.utcnow().date()
    buckets = {"0-30":0.0,"31-60":0.0,"61-90":0.0,"90+":0.0}
    rows = []
    with SessionLocal() as s:
        metas = s.query(OrderMeta).all()
        for m in metas:
            items = s.query(OrderItem).filter_by(order_code=m.order_code).all()
            charges = s.query(Charge).filter_by(order_code=m.order_code).all()
            pays = s.query(Payment).filter_by(order_code=m.order_code).all()
            principal = sum(c.amount for c in charges if c.kind=="PRINCIPAL")
            delivery  = sum(c.amount for c in charges if c.kind in ("DELIVERY_OUTBOUND","DELIVERY_RETURN"))
            penalty   = sum(c.amount for c in charges if c.kind=="PENALTY")
            credits   = sum(c.amount for c in charges if c.kind in ("BUYBACK_CREDIT","ADJUSTMENT"))
            accrual   = 0.0
            if m.type=="RENTAL" and m.plan_start_date:
                start = m.plan_start_date.date() if hasattr(m.plan_start_date,"date") else m.plan_start_date
                accrual = compute_rental_accrual(items, start, as_of)
            paid      = sum(p.amount for p in pays)
            total_due = principal + delivery + penalty + accrual + credits
            outstanding = round(max(0.0, total_due - paid),2)
            if outstanding <= 0: continue
            age_days = (as_of - (m.plan_start_date.date() if hasattr(m.plan_start_date,"date") else as_of)).days if m.plan_start_date else 0
            bucket = "0-30" if age_days<=30 else "31-60" if age_days<=60 else "61-90" if age_days<=90 else "90+"
            buckets[bucket] += outstanding
            rows.append({"code": m.order_code, "customer": m.customer_name, "type": m.type, "age_days": age_days, "outstanding": outstanding})
    return {"as_of": as_of.isoformat(), "buckets": buckets, "rows": rows}@app.get("/export/xlsx")
def export_xlsx(as_of: Optional[date] = None):
    as_of = as_of or datetime.utcnow().date()
    wb = Workbook(); ws = wb.active; ws.title = "OrderOps Export"
    headers = ["DocDate","DocNo","CustomerName","Phone","Address","LineType","SKU","ItemName","Qty","UnitPrice","RentMonthly","ChargeKind","Charge","Payment","Event","Outstanding"]
    ws.append(headers)
    with SessionLocal() as s:
        metas = s.query(OrderMeta).all()
        for m in metas:
            items = s.query(OrderItem).filter_by(order_code=m.order_code).all()
            charges = s.query(Charge).filter_by(order_code=m.order_code).all()
            pays = s.query(Payment).filter_by(order_code=m.order_code).all()
            events = s.query(Event).filter_by(order_code=m.order_code).all()
            principal = sum(c.amount for c in charges if c.kind=="PRINCIPAL")
            delivery  = sum(c.amount for c in charges if c.kind in ("DELIVERY_OUTBOUND","DELIVERY_RETURN"))
            penalty   = sum(c.amount for c in charges if c.kind=="PENALTY")
            credits   = sum(c.amount for c in charges if c.kind in ("BUYBACK_CREDIT","ADJUSTMENT"))
            accrual   = 0.0
            if m.type=="RENTAL" and m.plan_start_date:
                start = m.plan_start_date.date() if hasattr(m.plan_start_date,"date") else m.plan_start_date
                accrual = compute_rental_accrual(items, start, as_of)
            paid      = sum(p.amount for p in pays)
            total_due = principal + delivery + penalty + accrual + credits
            outstanding = round(max(0.0, total_due - paid),2)

            base = [as_of.isoformat(), m.order_code, m.customer_name, m.phone, (m.address or "").replace("\r"," ").replace("\n"," ")]
            for it in items:
                ws.append(base + ["ITEM", it.sku, it.name, it.qty, it.unit_price, it.rent_monthly, None, None, None, None, outstanding])
            for c in charges:
                ws.append(base + ["CHARGE", None, None, None, None, None, c.kind, c.amount, None, None, outstanding])
            for p in pays:
                ws.append(base + ["PAYMENT", None, None, None, None, None, None, None, p.amount, None, outstanding])
            for e in events:
                ws.append(base + ["EVENT", None, None, None, None, None, None, None, None, e.kind, outstanding])

    from io import BytesIO
    buf = BytesIO(); wb.save(buf); data = buf.getvalue()
    headers = {"Content-Disposition": f'attachment; filename="orderops-export-{as_of.isoformat()}.xlsx"'}
    return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)

# ## static-files-mount:begin (safe)
try:
    base_dir = Path(__file__).resolve().parent
    FILES_DIR = Path(os.getenv("FILES_DIR", str(base_dir.parent / "files")))
    os.makedirs(FILES_DIR, exist_ok=True)
    app.mount("/files", StaticFiles(directory=str(FILES_DIR)), name="files")
except Exception as _e:
    # Don't crash app if static mount fails; logs are enough
    import logging
    logging.warning(f"Static /files not mounted: {_e}")
# ## static-files-mount:end

