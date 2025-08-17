from alembic import op

# revision identifiers, used by Alembic.
revision = "3e5ced67facf"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Orders (create if not exists)
    op.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        code VARCHAR(50) NOT NULL,
        parent_order_id INTEGER,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        order_type VARCHAR(20) NOT NULL,
        event_type VARCHAR(20),
        status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
        customer_name VARCHAR(255),
        phone VARCHAR(64),
        address TEXT,
        location_url TEXT,
        subtotal NUMERIC(12,2) NOT NULL DEFAULT 0,
        discount NUMERIC(12,2) NOT NULL DEFAULT 0,
        delivery_fee NUMERIC(12,2) NOT NULL DEFAULT 0,
        return_delivery_fee NUMERIC(12,2) NOT NULL DEFAULT 0,
        penalty_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
        buyback_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
        total NUMERIC(12,2) NOT NULL DEFAULT 0,
        paid_initial NUMERIC(12,2) NOT NULL DEFAULT 0,
        to_collect_initial NUMERIC(12,2) NOT NULL DEFAULT 0,
        rental_monthly_total NUMERIC(12,2) NOT NULL DEFAULT 0,
        rental_start_date DATE,
        instalment_months_total INTEGER NOT NULL DEFAULT 0,
        instalment_monthly_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
        instalment_start_date DATE,
        notes TEXT
    );
    """)
    # FK + unique index if missing
    op.execute("""
    DO )
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='orders_parent_fk') THEN
            ALTER TABLE orders
              ADD CONSTRAINT orders_parent_fk FOREIGN KEY (parent_order_id)
              REFERENCES orders(id) ON DELETE SET NULL;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname='ix_orders_code') THEN
            CREATE UNIQUE INDEX ix_orders_code ON orders(code);
        END IF;
    END );
    """)

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
    op.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL,
        text TEXT,
        item_type VARCHAR(20),
        sku VARCHAR(128),
        name VARCHAR(255),
        qty NUMERIC(12,2) NOT NULL DEFAULT 1,
        unit_price NUMERIC(12,2) NOT NULL DEFAULT 0,
        line_total NUMERIC(12,2) NOT NULL DEFAULT 0,
        months INTEGER,
        monthly_amount NUMERIC(12,2),
        CONSTRAINT items_order_fk FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
    );
    """)
    op.execute("""
    DO )
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname='ix_items_order_id') THEN
            CREATE INDEX ix_items_order_id ON items(order_id);
        END IF;
    END );
    """)

    # Payments
    op.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL,
        amount NUMERIC(12,2) NOT NULL DEFAULT 0,
        method VARCHAR(30) NOT NULL DEFAULT 'CASH',
        reference VARCHAR(255),
        notes TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT payments_order_fk FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
    );
    """)
    op.execute("""
    DO )
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname='ix_payments_order_id') THEN
            CREATE INDEX ix_payments_order_id ON payments(order_id);
        END IF;
    END );
    """)

def downgrade():
    # Keep downgrade conservative
    pass