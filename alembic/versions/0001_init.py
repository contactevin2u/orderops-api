"""initial tables

Revision ID: 0001_init
Revises:
Create Date: 2025-08-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("parent_order_id", sa.Integer, sa.ForeignKey("orders.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("order_type", sa.String(length=20), nullable=False),  # OUTRIGHT/RENTAL/INSTALMENT
        sa.Column("event_type", sa.String(length=20), nullable=False),  # DELIVERY/RETURN
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("customer_name", sa.String(length=255)),
        sa.Column("phone", sa.String(length=50)),
        sa.Column("address", sa.Text()),
        sa.Column("location_url", sa.Text()),
        sa.Column("delivery_date", sa.Date()),
        sa.Column("return_date", sa.Date()),
        sa.Column("subtotal", sa.Numeric(12,2), server_default="0"),
        sa.Column("discount", sa.Numeric(12,2), server_default="0"),
        sa.Column("delivery_fee", sa.Numeric(12,2), server_default="0"),
        sa.Column("return_delivery_fee", sa.Numeric(12,2), server_default="0"),
        sa.Column("penalty_amount", sa.Numeric(12,2), server_default="0"),
        sa.Column("buyback_amount", sa.Numeric(12,2), server_default="0"),
        sa.Column("total", sa.Numeric(12,2), server_default="0"),
        sa.Column("paid_initial", sa.Numeric(12,2), server_default="0"),
        sa.Column("to_collect_initial", sa.Numeric(12,2), server_default="0"),
        sa.Column("rental_monthly_total", sa.Numeric(12,2), server_default="0"),
        sa.Column("rental_start_date", sa.Date()),
        sa.Column("instalment_months_total", sa.Integer, server_default="0"),
        sa.Column("instalment_monthly_amount", sa.Numeric(12,2), server_default="0"),
        sa.Column("instalment_start_date", sa.Date()),
        sa.Column("notes", sa.Text()),
    )
    op.create_index("ix_orders_code", "orders", ["code"], unique=True)

    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(length=20), nullable=False),   # RENTAL/INSTALMENT/OUTRIGHT/DELIVERY/RETURN_FEE etc
        sa.Column("text", sa.Text()),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sku", sa.String(length=64)),
        sa.Column("qty", sa.Integer, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12,2), server_default="0"),
        sa.Column("months", sa.Integer),
        sa.Column("monthly_amount", sa.Numeric(12,2)),
        sa.Column("line_total", sa.Numeric(12,2), server_default="0"),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12,2), nullable=False),
        sa.Column("method", sa.String(length=50)),        # CASH, FPX, CHEQUE, TNG, etc.
        sa.Column("reference", sa.String(length=100)),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("void_reason", sa.Text()),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source", sa.String(length=50)),        # e.g. 'whatsapp'
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), unique=True),
        sa.Column("parsed_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

def downgrade():
    op.drop_table("messages")
    op.drop_table("payments")
    op.drop_table("order_items")
    op.drop_index("ix_orders_code", table_name="orders")
    op.drop_table("orders")