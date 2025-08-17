"""init tables

Revision ID: 0001_init
Revises: 
Create Date: 2025-08-17

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_init'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('parent_order_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('order_type', sa.Enum('OUTRIGHT','RENTAL','INSTALMENT','ADJUSTMENT', name='ordertype'), nullable=True),
        sa.Column('event_type', sa.Enum('DELIVERY','RETURN','INSTALMENT_CANCEL','BUYBACK','ADJUSTMENT', name='eventtype'), nullable=True),
        sa.Column('status', sa.Enum('ACTIVE','RETURNED','CANCELLED','COMPLETED', name='orderstatus'), nullable=True),
        sa.Column('customer_name', sa.String(length=200), nullable=False),
        sa.Column('phone', sa.String(length=64), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('location_url', sa.Text(), nullable=True),
        sa.Column('subtotal', sa.Numeric(12,2), nullable=True),
        sa.Column('discount', sa.Numeric(12,2), nullable=True),
        sa.Column('delivery_fee', sa.Numeric(12,2), nullable=True),
        sa.Column('return_delivery_fee', sa.Numeric(12,2), nullable=True),
        sa.Column('penalty_amount', sa.Numeric(12,2), nullable=True),
        sa.Column('buyback_amount', sa.Numeric(12,2), nullable=True),
        sa.Column('total', sa.Numeric(12,2), nullable=True),
        sa.Column('paid_initial', sa.Numeric(12,2), nullable=True),
        sa.Column('to_collect_initial', sa.Numeric(12,2), nullable=True),
        sa.Column('rental_monthly_total', sa.Numeric(12,2), nullable=True),
        sa.Column('rental_start_date', sa.DateTime(), nullable=True),
        sa.Column('instalment_months_total', sa.Integer(), nullable=True),
        sa.Column('instalment_monthly_amount', sa.Numeric(12,2), nullable=True),
        sa.Column('instalment_start_date', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index(op.f('ix_orders_code'), 'orders', ['code'], unique=False)
    op.create_table('messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('parsed_json', sa.Text(), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sha256')
    )
    op.create_index(op.f('ix_messages_sha256'), 'messages', ['sha256'], unique=False)
    op.create_table('order_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('sku', sa.String(length=64), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('qty', sa.Numeric(12,2), nullable=True),
        sa.Column('unit_price', sa.Numeric(12,2), nullable=True),
        sa.Column('line_total', sa.Numeric(12,2), nullable=True),
        sa.Column('item_type', sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('amount', sa.Numeric(12,2), nullable=False),
        sa.Column('method', sa.Enum('CASH','TRANSFER','TNG','CHEQUE','CARD','OTHER', name='paymentmethod'), nullable=True),
        sa.Column('reference', sa.String(length=128), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('voided', sa.Boolean(), nullable=True),
        sa.Column('void_reason', sa.Text(), nullable=True),
        sa.Column('voided_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('payments')
    op.drop_table('order_items')
    op.drop_index(op.f('ix_messages_sha256'), table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('ix_orders_code'), table_name='orders')
    op.drop_table('orders')
