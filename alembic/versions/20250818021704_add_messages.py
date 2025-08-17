from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "3e5c_add_messages"  # any unique id
down_revision = "3e5ced67facf"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("parsed_json", JSONB, nullable=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_messages_sha256", "messages", ["sha256"], unique=True)
    op.create_index("ix_messages_order_id", "messages", ["order_id"], unique=False)

def downgrade():
    op.drop_index("ix_messages_order_id", table_name="messages")
    op.drop_index("ix_messages_sha256", table_name="messages")
    op.drop_table("messages")