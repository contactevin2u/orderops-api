"""Add deliveries and audit_logs (parity with storage layer)"""

from alembic import op
import sqlalchemy as sa

revision = "0002_ops_extras"
down_revision = "0001_init"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("deliveries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), index=True),
        sa.Column("outbound_date", sa.Date()),
        sa.Column("outbound_time", sa.String(length=8)),
        sa.Column("return_date", sa.Date()),
        sa.Column("return_time", sa.String(length=8)),
        sa.Column("status", sa.String(length=24), server_default="SCHEDULED"),
        sa.Column("notes", sa.Text),
    )
    op.create_table("audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), index=True),
        sa.Column("action", sa.String(length=64)),
        sa.Column("meta", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

def downgrade():
    op.drop_table("audit_logs")
    op.drop_table("deliveries")