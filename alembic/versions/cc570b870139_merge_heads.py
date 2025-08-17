"""merge heads to unify migration graph

Revision ID: cc570b870139
Revises: 0002_ops_extras, 1f1b66ee3e31
Create Date: 2025-08-17 12:41:29
"""
from alembic import op
import sqlalchemy as sa

revision = "cc570b870139"
down_revision = ('0002_ops_extras', '1f1b66ee3e31',)
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass