\"\"\"merge heads to unify migration graph

Revision ID: 222b3db5248c
Revises: 0002_ops_extras, 1f1b66ee3e31
Create Date: 2025-08-17 12:38:31
\"\"\"
from alembic import op
import sqlalchemy as sa

revision = "222b3db5248c"
down_revision = ('0002_ops_extras', '1f1b66ee3e31',)
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass