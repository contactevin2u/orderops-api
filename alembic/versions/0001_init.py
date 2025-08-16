"""Initial database schema for OrderOps"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_init'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('customers',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(length=200), nullable=False, index=True),
        sa.Column('phone', sa.String(length=50), index=True),
        sa.Column('phone_norm', sa.String(length=32), index=True),
        sa.Column('address', sa.Text)
    )
    ord_type = sa.Enum('RENTAL', 'INSTALMENT', 'OUTRIGHT', name='ordertype')
    evt_type = sa.Enum('NONE', 'RETURN', 'COLLECT', 'INSTALMENT_CANCEL', 'BUYBACK', name='eventtype')
    ord_status = sa.Enum('DRAFT', 'CONFIRMED', 'RETURNED', 'CANCELLED', name='orderstatus')
    led_kind = sa.Enum('INITIAL_CHARGE', 'MONTHLY_CHARGE', 'ADJUSTMENT', name='ledgerkind')

    op.create_table('orders',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('order_code', sa.String(length=64), unique=True, index=True, nullable=False),
        sa.Column('external_id', sa.String(length=80), unique=True, index=True),
        sa.Column('parent_id', sa.Integer, sa.ForeignKey('orders.id'), index=True),
        sa.Column('customer_id', sa.Integer, sa.ForeignKey('customers.id'), index=True),
        sa.Column('type', ord_type, nullable=False),
        sa.Column('status', ord_status, server_default='CONFIRMED', index=True),
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('due_date', sa.Date()),
        sa.Column('return_due_date', sa.Date()),
        sa.Column('returned_at', sa.DateTime(timezone=True)),
        sa.Column('collected_at', sa.DateTime(timezone=True))
    )
    op.create_table('order_items',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('order_id', sa.Integer, sa.ForeignKey('orders.id'), index=True),
        sa.Column('sku', sa.String(length=64)),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('qty', sa.Integer),
        sa.Column('unit_price', sa.Numeric(12, 2), server_default='0')
    )
    op.create_table('payments',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('order_id', sa.Integer, sa.ForeignKey('orders.id'), index=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('method', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'))
    )
    op.create_table('events',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('order_id', sa.Integer, sa.ForeignKey('orders.id'), index=True),
        sa.Column('type', evt_type),
        sa.Column('reason', sa.Text),
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'))
    )
    op.create_table('payment_plans',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('order_id', sa.Integer, sa.ForeignKey('orders.id'), index=True),
        sa.Column('cadence', sa.String(length=20), server_default='MONTHLY'),
        sa.Column('term_months', sa.Integer),
        sa.Column('monthly_amount', sa.Numeric(12, 2)),
        sa.Column('start_date', sa.Date()),
        sa.Column('end_date', sa.Date()),
        sa.Column('active', sa.Integer, server_default='1')
    )
    op.create_table('ledger_entries',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('order_id', sa.Integer, sa.ForeignKey('orders.id'), index=True),
        sa.Column('kind', led_kind),
        sa.Column('amount', sa.Numeric(12, 2)),
        sa.Column('period', sa.String(length=7)),
        sa.Column('entry_date', sa.Date(), server_default=sa.text('CURRENT_DATE')),
        sa.Column('note', sa.Text)
    )
    op.create_table('idempotency_keys',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('key', sa.String(length=128), unique=True, nullable=False),
        sa.Column('method', sa.String(length=8)),
        sa.Column('path', sa.Text),
        sa.Column('status_code', sa.Integer),
        sa.Column('response_body', sa.LargeBinary),
        sa.Column('content_type', sa.String(length=100))
    )
    op.create_table('code_reservations',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('code', sa.String(length=64), unique=True, nullable=False)
    )
    op.create_table('jobs',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('job_id', sa.String(length=64), unique=True),
        sa.Column('kind', sa.String(length=20)),
        sa.Column('status', sa.String(length=20)),
        sa.Column('result_url', sa.Text),
        sa.Column('error', sa.Text)
    )

def downgrade():
    op.drop_table('jobs')
    op.drop_table('code_reservations')
    op.drop_table('idempotency_keys')
    op.drop_table('ledger_entries')
    op.drop_table('payment_plans')
    op.drop_table('events')
    op.drop_table('payments')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('customers')
