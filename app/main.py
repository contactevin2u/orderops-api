from fastapi import FastAPI, Depends, HTTPException, Body, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List, Optional
from datetime import datetime, timezone
import hashlib, json, io
import pandas as pd

from .config import get_settings
from .db import Base, engine, get_db
from .models import Order, OrderItem, Payment, Message, OrderType, EventType, OrderStatus, PaymentMethod
from .schemas import ParsedOrder, ManualOrderCreate, OrderOut, PaymentCreate, OrderItemOut, PaymentOut
from .parsing import parse_message
from .products import map_product
from .utils import months_elapsed_no_prorate
from .pdf import invoice_pdf, receipt_pdf, instalment_agreement_pdf

settings = get_settings()
app = FastAPI(title="Order Intake Suite", version="1.0")

# CORS
origins = ["*"] if settings.cors_origins == "*" else [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB init (dev convenience)
Base.metadata.create_all(bind=engine)

def now_utc():
    return datetime.now(timezone.utc)

def generate_order_code(db: Session) -> str:
    today = datetime.utcnow().strftime("%y%m%d")
    prefix = f"KP{today}-"
    last = db.execute(select(Order).where(Order.code.like(prefix + "%")).order_by(Order.id.desc())).scalars().first()
    if last and last.code.startswith(prefix):
        try:
            n = int(last.code.split("-")[-1]) + 1
        except Exception:
            n = 1
    else:
        n = 1
    return f"{prefix}{n:03d}"

def compute_outstanding(order: Order, db: Session) -> float:
    payments_sum = float(db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.order_id == order.id, Payment.voided == False)
    ).scalar_one() or 0.0)

    expected = float(order.total or 0)

    if order.order_type == OrderType.RENTAL:
        # Include recurring from month 2 onwards
        if order.rental_start_date and float(order.rental_monthly_total) > 0:
            months = months_elapsed_no_prorate(order.rental_start_date, now_utc())
            if months > 1:
                expected += (months - 1) * float(order.rental_monthly_total)
    elif order.order_type == OrderType.INSTALMENT:
        if order.instalment_start_date and order.instalment_months_total and order.instalment_monthly_amount:
            months = months_elapsed_no_prorate(order.instalment_start_date, now_utc())
            months = min(months, int(order.instalment_months_total))
            expected = months * float(order.instalment_monthly_amount)

    # Adjustments from child orders
    children = db.execute(select(Order).where(Order.parent_order_id == order.id)).scalars().all()
    for ch in children:
        expected += float(ch.total or 0)

    return max(expected - payments_sum, 0.0)

def order_to_out(order: Order, db: Session) -> OrderOut:
    return OrderOut(
        id=order.id,
        code=order.code,
        parent_order_id=order.parent_order_id,
        created_at=order.created_at,
        order_type=order.order_type.value,
        event_type=order.event_type.value,
        status=order.status.value,
        customer_name=order.customer_name,
        phone=order.phone,
        address=order.address,
        location_url=order.location_url,
        subtotal=float(order.subtotal or 0),
        discount=float(order.discount or 0),
        delivery_fee=float(order.delivery_fee or 0),
        return_delivery_fee=float(order.return_delivery_fee or 0),
        penalty_amount=float(order.penalty_amount or 0),
        buyback_amount=float(order.buyback_amount or 0),
        total=float(order.total or 0),
        paid_initial=float(order.paid_initial or 0),
        to_collect_initial=float(order.to_collect_initial or 0),
        rental_monthly_total=float(order.rental_monthly_total or 0),
        rental_start_date=order.rental_start_date,
        instalment_months_total=int(order.instalment_months_total or 0),
        instalment_monthly_amount=float(order.instalment_monthly_amount or 0),
        instalment_start_date=order.instalment_start_date,
        notes=order.notes,
        items=[OrderItemOut.model_validate(it) for it in order.items],
        payments=[PaymentOut.model_validate(p) for p in order.payments],
        outstanding_estimate=compute_outstanding(order, db),
    )

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/parse", response_model=ParsedOrder)
def parse(text: str = Body(..., media_type="text/plain"), db: Session = Depends(get_db)):
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    msg = db.query(Message).filter(Message.sha256 == sha).first()
    if msg and msg.parsed_json:
        try:
            return json.loads(msg.parsed_json)
        except Exception:
            pass

    parsed = parse_message(text)

    # --- sanitize items (safe defaults) ---
    items = parsed.get("items", []) or []
    for item in items:
        if item.get("text") is None:
            item["text"] = item.get("name") or ""
        if item.get("item_type") is None:
            item["item_type"] = "OUTRIGHT"
        if item.get("line_total") is None and item.get("qty") is not None and item.get("unit_price") is not None:
            try:
                item["line_total"] = float(item["qty"]) * float(item["unit_price"])
            except Exception:
                pass
    parsed["items"] = items

    # Map SKUs
    for item in parsed.get("items", []):
        mapped = map_product(item.get("text", "") or item.get("name", ""))
        if not item.get("sku") and mapped.get("sku"):
            item["sku"] = mapped["sku"]
        if not item.get("name") and mapped.get("name"):
            item["name"] = mapped["name"]

    # Persist message + parsed
    m = Message(sha256=sha, text=text, parsed_json=json.dumps(parsed))
    db.add(m); db.commit()
    return parsed

def create_order_from_parsed(parsed: ParsedOrder, db: Session) -> Order:
    # Coerce defaults
    order_code = parsed.order_code or generate_order_code(db)
    event_type = EventType(parsed.event_type or "DELIVERY")
    # Determine order_type by items majority / business rules
    types = [i.item_type for i in parsed.items]
    otype = OrderType.OUTRIGHT
    if "RENTAL" in types:
        otype = OrderType.RENTAL
    elif "INSTALMENT" in types:
        otype = OrderType.INSTALMENT

    order = Order(
        code=order_code,
        order_type=otype,
        event_type=event_type,
        status=OrderStatus.ACTIVE,
        customer_name=parsed.customer_name or "Unknown",
        phone=parsed.phone,
        address=parsed.address,
        location_url=parsed.location_url,
        notes=parsed.notes,
    )

    subtotal = 0.0
    rental_monthly_total = 0.0
    instalment_months = 0
    instalment_monthly = 0.0

    for it in parsed.items:
        name = it.name or it.text
        qty = it.qty or 1
        unit = it.unit_price or 0
        total = it.line_total if it.line_total is not None else (qty * unit)
        item = OrderItem(
            sku=it.sku, name=name, qty=qty, unit_price=unit, line_total=total, item_type=it.item_type
        )
        order.items.append(item)
        subtotal += float(total or 0)

        if it.item_type == "RENTAL":
            monthly = it.monthly_amount or unit or 0
            rental_monthly_total += float(monthly)
            if parsed.delivery_date:
                order.rental_start_date = parsed.delivery_date
        if it.item_type == "INSTALMENT":
            instalment_months = it.months or instalment_months
            instalment_monthly = it.monthly_amount or unit or instalment_monthly
            if parsed.delivery_date:
                order.instalment_start_date = parsed.delivery_date

    order.subtotal = subtotal
    order.discount = float(parsed.discount or 0)
    order.delivery_fee = float(parsed.delivery_fee or 0)
    order.return_delivery_fee = float(parsed.return_delivery_fee or 0)
    order.penalty_amount = float(parsed.penalty_amount or 0)
    order.buyback_amount = float(parsed.buyback_amount or 0)

    order.total = float(parsed.total or (subtotal - order.discount + order.delivery_fee + order.return_delivery_fee + order.penalty_amount + order.buyback_amount))
    order.paid_initial = float(parsed.paid or 0)
    order.to_collect_initial = float(parsed.to_collect or max(order.total - order.paid_initial, 0))

    order.rental_monthly_total = rental_monthly_total
    order.instalment_months_total = int(instalment_months or 0)
    order.instalment_monthly_amount = float(instalment_monthly or 0)

    db.add(order); db.commit(); db.refresh(order)

    # Auto-create initial payment record if paid_initial > 0
    if order.paid_initial and order.paid_initial > 0:
        p = Payment(order_id=order.id, amount=order.paid_initial, method=PaymentMethod.CASH, reference="init")
        db.add(p); db.commit()
    return order

@app.post("/orders", response_model=OrderOut)
def create_order(payload: ManualOrderCreate, db: Session = Depends(get_db)):
    parsed = payload.parsed
    order = create_order_from_parsed(parsed, db)
    return order_to_out(order, db)

@app.get("/orders", response_model=List[OrderOut])
def list_orders(status: Optional[str] = None, q: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Order)
    if status:
        try:
            query = query.filter(Order.status == OrderStatus(status))
        except Exception:
            pass
    if q:
        like = f"%{q}%"
        query = query.filter((Order.code.ilike(like)) | (Order.customer_name.ilike(like)) | (Order.phone.ilike(like)))
    query = query.order_by(Order.id.desc()).limit(2000)
    rows = query.all()
    return [order_to_out(o, db) for o in rows]

@app.patch("/orders/{order_id}", response_model=OrderOut)
def edit_order(order_id: int, payload: dict, db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, "Order not found")
    for k, v in payload.items():
        if hasattr(o, k):
            setattr(o, k, v)
    o.updated_at = now_utc()
    db.commit(); db.refresh(o)
    return order_to_out(o, db)

@app.post("/orders/{order_id}/payments", response_model=PaymentOut)
def add_payment(order_id: int, data: PaymentCreate, db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, "Order not found")
    p = Payment(order_id=order_id, amount=data.amount, method=PaymentMethod(data.method), reference=data.reference, notes=data.notes)
    db.add(p); db.commit(); db.refresh(p)
    return PaymentOut.model_validate(p)

@app.post("/payments/{payment_id}/void", response_model=PaymentOut)
def void_payment(payment_id: int, reason: str = Body(""), db: Session = Depends(get_db)):
    p = db.get(Payment, payment_id)
    if not p:
        raise HTTPException(404, "Payment not found")
    p.voided = True
    p.void_reason = reason or "voided"
    p.voided_at = now_utc()
    db.commit(); db.refresh(p)
    return PaymentOut.model_validate(p)

def _create_adjustment_child(parent: Order, suffix: str, total: float, notes: str, db: Session) -> Order:
    child = Order(
        code=f"{parent.code}{suffix}",
        parent_order_id=parent.id,
        order_type=OrderType.ADJUSTMENT,
        event_type=EventType.ADJUSTMENT,
        status=parent.status,
        customer_name=parent.customer_name,
        phone=parent.phone,
        address=parent.address,
        location_url=parent.location_url,
        subtotal=0, discount=0, delivery_fee=0, return_delivery_fee=0,
        penalty_amount=0, buyback_amount=0,
        total=total, notes=notes
    )
    db.add(child); db.commit(); db.refresh(child)
    return child

@app.post("/orders/{order_id}/cancel_instalment", response_model=OrderOut)
def cancel_instalment(order_id: int, penalty_amount: float = Body(..., embed=True), return_delivery_fee: float = Body(0.0, embed=True), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, "Order not found")
    if o.order_type != OrderType.INSTALMENT:
        raise HTTPException(400, "Not an instalment order")
    # Outstanding balance for the instalment plan
    months_paid = 0
    # Approx: infer by sum(payments)/monthly_amount (ignoring upfront)
    if o.instalment_monthly_amount:
        paid = sum(float(p.amount) for p in o.payments if not p.voided)
        months_paid = int(paid // float(o.instalment_monthly_amount))
    balance = max(float(o.instalment_months_total)*float(o.instalment_monthly_amount) - (months_paid*float(o.instalment_monthly_amount)), 0.0)
    # Create adjustment: -balance + penalty + return fee
    total = -balance + penalty_amount + return_delivery_fee
    child = _create_adjustment_child(o, "-I", total, f"Instalment cancel: -balance {balance:.2f} + penalty {penalty_amount:.2f} + return fee {return_delivery_fee:.2f}", db)
    o.status = OrderStatus.CANCELLED
    db.commit(); db.refresh(o)
    return order_to_out(child, db)

@app.post("/orders/{order_id}/return_rental", response_model=OrderOut)
def return_rental(order_id: int, return_delivery_fee: float = Body(..., embed=True), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, "Order not found")
    if o.order_type != OrderType.RENTAL:
        raise HTTPException(400, "Not a rental order")
    child = _create_adjustment_child(o, "-R", return_delivery_fee, f"Rental return collection fee", db)
    o.status = OrderStatus.RETURNED
    db.commit(); db.refresh(o)
    return order_to_out(child, db)

@app.post("/orders/{order_id}/buyback", response_model=OrderOut)
def buyback(order_id: int, buyback_amount: float = Body(..., embed=True), return_delivery_fee: float = Body(0.0, embed=True), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, "Order not found")
    # Convention: buyback_amount as negative number (credit to customer). Here we follow: negative credit + return fee (positive).
    total = float(buyback_amount) + float(return_delivery_fee)
    child = _create_adjustment_child(o, "-B", total, f"Buyback + return fee", db)
    o.status = OrderStatus.CANCELLED if o.order_type == OrderType.OUTRIGHT else o.status
    db.commit(); db.refresh(o)
    return order_to_out(child, db)

@app.get("/orders/{order_id}/invoice.pdf")
def invoice(order_id: int, db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, "Order not found")
    pdf = invoice_pdf(o)
    return Response(content=pdf, media_type="application/pdf")

@app.get("/payments/{payment_id}/receipt.pdf")
def receipt(payment_id: int, db: Session = Depends(get_db)):
    p = db.get(Payment, payment_id)
    if not p:
        raise HTTPException(404, "Payment not found")
    o = db.get(Order, p.order_id)
    pdf = receipt_pdf(o, p)
    return Response(content=pdf, media_type="application/pdf")

@app.get("/orders/{order_id}/instalment-agreement.pdf")
def instalment_agreement(order_id: int, db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, "Order not found")
    if o.order_type != OrderType.INSTALMENT:
        raise HTTPException(400, "Not an instalment order")
    pdf = instalment_agreement_pdf(o)
    return Response(content=pdf, media_type="application/pdf")

@app.get("/export/cash.xlsx")
def export_cash(start: str, end: str, db: Session = Depends(get_db)):
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    rows = db.query(Payment).filter(Payment.created_at >= start_dt, Payment.created_at <= end_dt).all()

    data = []
    for p in rows:
        if p.voided:
            continue
        o = db.get(Order, p.order_id)
        data.append({
            "date": p.created_at.date().isoformat(),
            "order_code": o.code if o else "",
            "customer_name": o.customer_name if o else "",
            "amount": float(p.amount),
            "method": p.method.value,
            "reference": p.reference or "",
            "parent_order": o.parent_order_id or "",
        })
    df = pd.DataFrame(data)
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="cash", index=False)
    bio.seek(0)
    return Response(content=bio.read(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

