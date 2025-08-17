from alembic import op

# no autogenerate here; do it defensively for Postgres
def upgrade() -> None:
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS reference VARCHAR(120)")
    

def downgrade() -> None:
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS reference")