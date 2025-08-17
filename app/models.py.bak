from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Numeric, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ENUM
from .db import Base

class OrderType(Enum):
    RENTAL = "RENTAL"
    INSTALMENT = "INSTALMENT"
    OUTRIGHT = "OUTRIGHT"

class OrderStatus(Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    RETURNED = "RETURNED"
    CANCELLED = "CANCELLED"

class EventType(Enum):
    NONE = "NONE"
    RETURN = "RETURN"
    COLLECT = "COLLECT"
    INSTALMENT_CANCEL = "INSTALMENT_CANCEL"
    BUYBACK = "BUYBACK"

class LedgerKind(Enum):
    INITIAL_CHARGE = "INITIAL_CHARGE"
    MONTHLY_CHARGE = "MONTHLY_CHARGE"
    ADJUSTMENT = "ADJUSTMENT"

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    phone = Column(String(50))
    phone_norm = Column(String(32))
    address = Column(Text)

    orders = relationship("Order", back_populates="customer")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_code = Column(String(64), nullable=False, unique=True, index=True)
    external_id = Column(String(80), unique=True, index=True)
    parent_id = Column(Integer, ForeignKey("orders.id"))
    customer_id = Column(Integer, ForeignKey("customers.id"))
    type = Column(ENUM(OrderType), nullable=False)
    status = Column(ENUM(OrderStatus), default=OrderStatus.CONFIRMED, index=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    due_date = Column(Date)
    return_due_date = Column(Date)
    returned_at = Column(DateTime(timezone=True))
    collected_at = Column(DateTime(timezone=True))

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="order", cascade="all, delete-orphan")
    plan = relationship("PaymentPlan", back_populates="order", uselist=False, cascade="all, delete-orphan")
    ledger = relationship("LedgerEntry", back_populates="order", cascade="all, delete-orphan")
    parent = relationship("Order", remote_side=[id])

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    sku = Column(String(64))
    name = Column(String(200), nullable=False)
    qty = Column(Integer)
    unit_price = Column(Numeric(12, 2), default=0)

    order = relationship("Order", back_populates="items")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    method = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    order = relationship("Order", back_populates="payments")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    type = Column(ENUM(EventType))
    reason = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    order = relationship("Order", back_populates="events")

class PaymentPlan(Base):
    __tablename__ = "payment_plans"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    cadence = Column(String(20), default="MONTHLY")
    term_months = Column(Integer)
    monthly_amount = Column(Numeric(12, 2))
    start_date = Column(Date)
    end_date = Column(Date)
    active = Column(Integer, default=1)

    order = relationship("Order", back_populates="plan")

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    kind = Column(ENUM(LedgerKind))
    amount = Column(Numeric(12, 2))
    period = Column(String(7))
    entry_date = Column(Date, default=date.today)
    note = Column(Text)

    order = relationship("Order", back_populates="ledger")

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    id = Column(Integer, primary_key=True)
    key = Column(String(128), nullable=False, unique=True)
    method = Column(String(8))
    path = Column(Text)
    status_code = Column(Integer)
    response_body = Column(LargeBinary)
    content_type = Column(String(100))

class CodeReservation(Base):
    __tablename__ = "code_reservations"
    id = Column(Integer, primary_key=True)
    code = Column(String(64), nullable=False, unique=True)

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    job_id = Column(String(64), unique=True)
    kind = Column(String(20))
    status = Column(String(20))
    result_url = Column(Text)
    error = Column(Text)
