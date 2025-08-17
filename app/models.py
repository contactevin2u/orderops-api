from sqlalchemy import Column, Integer, String, DateTime, Date, Enum, ForeignKey, Numeric, JSON, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base

OrderType = Enum("OUTRIGHT","INSTALMENT","RENTAL", name="order_type", native_enum=False)
OrderStatus = Enum("CONFIRMED","RETURNED","CANCELLED", name="order_status", native_enum=False)
LedgerKind = Enum("INITIAL_CHARGE","DELIVERY_OUTBOUND","DELIVERY_RETURN","RENTAL_MONTHLY","INSTALMENT_MONTHLY","PENALTY","BUYBACK_CREDIT","ADJUSTMENT", name="ledger_kind", native_enum=False)
EventType = Enum("RETURN","COLLECT","INSTALMENT_CANCEL","BUYBACK", name="event_type", native_enum=False)
PaymentStatus = Enum("POSTED","VOIDED", name="payment_status", native_enum=False)

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True)
    address = Column(String)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_code = Column(String, unique=True, nullable=False)
    type = Column(OrderType, nullable=False)
    status = Column(OrderStatus, nullable=False, default="CONFIRMED")
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    customer = relationship("Customer")
    items = relationship("OrderItem", cascade="all, delete-orphan")
    payments = relationship("Payment", cascade="all, delete-orphan")
    events = relationship("Event", cascade="all, delete-orphan")
    ledger = relationship("LedgerEntry", cascade="all, delete-orphan")
    deliveries = relationship("Delivery", cascade="all, delete-orphan")
    plan = relationship("PaymentPlan", uselist=False, cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    sku = Column(String)
    name = Column(String, nullable=False)
    qty = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(12,2))
    rent_monthly = Column(Numeric(12,2))
    buyback_rate = Column(Numeric(5,2))

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    amount = Column(Numeric(12,2), nullable=False)
    method = Column(String, default="CASH")
    status = Column(PaymentStatus, default="POSTED", nullable=False)
    reference = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    voided_at = Column(DateTime)
    void_reason = Column(String)

class PaymentPlan(Base):
    __tablename__ = "payment_plans"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    cadence = Column(String, default="MONTHLY", nullable=False)
    term_months = Column(Integer)
    monthly_amount = Column(Numeric(12,2))
    start_date = Column(Date)

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    kind = Column(LedgerKind, nullable=False)
    amount = Column(Numeric(12,2), nullable=False)
    note = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class Delivery(Base):
    __tablename__ = "deliveries"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    outbound_date = Column(Date)
    outbound_time = Column(String)
    return_date = Column(Date)
    return_time = Column(String)
    status = Column(String, default="SCHEDULED")
    outbound_fee = Column(Numeric(12,2))
    return_fee = Column(Numeric(12,2))

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    type = Column(EventType, nullable=False)
    payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    action = Column(String, nullable=False)
    meta = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False)
    method = Column(String, nullable=False)
    path = Column(String, nullable=False)
    status_code = Column(Integer)
    response_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("key","method","path", name="uq_idem_triple"),
    )
