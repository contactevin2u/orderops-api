from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base

# Helper to stay tolerant if DB columns are plain strings instead of SQL ENUMs
def _val(x): 
    try: 
        return x.value
    except Exception:
        return x

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    phone = Column(String(64), index=True)
    address = Column(Text)
    orders = relationship("Order", back_populates="customer")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_code = Column(String(64), unique=True, index=True)
    type = Column(String(16))          # OUTRIGHT | INSTALMENT | RENTAL
    status = Column(String(16), default="CONFIRMED")  # CONFIRMED | RETURNED | CANCELLED
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    customer_id = Column(Integer, ForeignKey("customers.id"))
    customer = relationship("Customer", back_populates="orders")

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="order", cascade="all, delete-orphan")
    ledger = relationship("LedgerEntry", back_populates="order", cascade="all, delete-orphan")
    plan = relationship("PaymentPlan", back_populates="order", uselist=False, cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    sku = Column(String(64))
    name = Column(String(255))
    qty = Column(Integer, default=1)
    unit_price = Column(Numeric(12,2), default=0)

    order = relationship("Order", back_populates="items")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    amount = Column(Numeric(12,2))
    method = Column(String(32), default="CASH")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    order = relationship("Order", back_populates="payments")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    type = Column(String(32))  # RETURN | COLLECT | INSTALMENT_CANCEL | BUYBACK
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    order = relationship("Order", back_populates="events")

class PaymentPlan(Base):
    __tablename__ = "payment_plans"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    cadence = Column(String(16), default="MONTHLY")
    term_months = Column(Integer)
    monthly_amount = Column(Numeric(12,2))
    start_date = Column(Date)

    order = relationship("Order", back_populates="plan")

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    kind = Column(String(32))  # INITIAL_CHARGE | ADJUSTMENT
    amount = Column(Numeric(12,2), default=0)
    note = Column(Text)

    order = relationship("Order", back_populates="ledger")

class Delivery(Base):
    __tablename__ = "deliveries"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    outbound_date = Column(Date)
    outbound_time = Column(String(8))
    return_date = Column(Date)
    return_time = Column(String(8))
    status = Column(String(24), default="SCHEDULED")  # SCHEDULED|DONE|CANCELLED
    notes = Column(Text)

    order = relationship("Order")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    action = Column(String(64))
    meta = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    order = relationship("Order")

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    id = Column(Integer, primary_key=True)
    key = Column(String(64), unique=True, index=True)
    method = Column(String(8))
    path = Column(String(256))
    status_code = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)