"""Merge two alembic heads into one."""

# revision identifiers, used by Alembic.
revision = "merge_20250818005722"
down_revision = ("0001_init", "3e5ced67facf")
branch_labels = None
depends_on = None

def upgrade():
    # No-op; this just merges heads
    pass

def downgrade():
    # No-op
    pass