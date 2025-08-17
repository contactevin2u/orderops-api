from sqlalchemy import (
    Column, Integer, String, DateTime, Enum, ForeignKey, Numeric, Text, Boolean
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
import enum
from .db import Base

class OrderType(str, enum.Enum):
    OUTRIGHT = "OUTRIGHT"
    RENTAL = "RENTAL"
    INSTALMENT = "INSTALMENT"
    ADJUSTMENT = "ADJUSTMENT"

class EventType(str, enum.Enum):
    DELIVERY = "DELIVERY"
    RETURN = "RETURN"
    INSTALMENT_CANCEL = "INSTALMENT_CANCEL"
    BUYBACK = "BUYBACK"
    ADJUSTMENT = "ADJUSTMENT"

class OrderStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    RETURNED = "RETURNED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"

class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    TRANSFER = "TRANSFER"
    TNG = "TNG"  # Touch 'n Go / e-wallet
    CHEQUE = "CHEQUE"
    CARD = "CARD"
    OTHER = "OTHER"

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    parent_order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order_type: Mapped[OrderType] = mapped_column(Enum(OrderType), default=OrderType.OUTRIGHT, index=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), default=EventType.DELIVERY, index=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.ACTIVE, index=True)

    customer_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Commercials
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    discount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    delivery_fee: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    return_delivery_fee: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    penalty_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    buyback_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)  # Negative credit or positive charge depending on business rule
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    paid_initial: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    to_collect_initial: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    # Rental
    rental_monthly_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    rental_start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Instalment
    instalment_months_total: Mapped[int] = mapped_column(Integer, default=0)
    instalment_monthly_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    instalment_start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="order", cascade="all, delete-orphan")
    parent_order: Mapped["Order | None"] = relationship("Order", remote_side=[id])

class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"))
    sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    qty: Mapped[float] = mapped_column(Numeric(12, 2), default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    line_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    item_type: Mapped[str] = mapped_column(String(32), default="OUTRIGHT")  # OUTRIGHT | RENTAL | INSTALMENT

    order: Mapped["Order"] = relationship("Order", back_populates="items")

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), default=PaymentMethod.CASH)
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    voided: Mapped[bool] = mapped_column(Boolean, default=False)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="payments")

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    text: Mapped[str] = mapped_column(Text)
    parsed_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

