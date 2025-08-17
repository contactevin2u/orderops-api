from alembic import op

# revision identifiers, used by Alembic.
revision = "3e5ced67facf"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Orders (create if not exists)
    

    # Safety net: add missing columns
    for sql in [
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS address TEXT",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS buyback_amount NUMERIC(12,2) NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_name VARCHAR(255)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_fee NUMERIC(12,2) NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount NUMERIC(12,2) NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS event_type VARCHAR(20)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS instalment_monthly_amount NUMERIC(12,2) NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS instalment_months_total INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS instalment_start_date DATE",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS location_url TEXT",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_type VARCHAR(20) NOT NULL DEFAULT 'OUTRIGHT'",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS paid_initial NUMERIC(12,2) NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS parent_order_id INTEGER",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS penalty_amount NUMERIC(12,2) NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS phone VARCHAR(64)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS rental_monthly_total NUMERIC(12,2) NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS rental_start_date DATE",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS return_delivery_fee NUMERIC(12,2) NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS subtotal NUMERIC(12,2) NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS to_collect_initial NUMERIC(12,2) NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS total NUMERIC(12,2) NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS notes TEXT"
    ]:
        op.execute(sql)

    # Items
    

    # Payments
    op.create_index('ix_orders_code','orders',['code'],unique=True,if_not_exists=True)

def downgrade():
    # Keep downgrade conservative
    pass

