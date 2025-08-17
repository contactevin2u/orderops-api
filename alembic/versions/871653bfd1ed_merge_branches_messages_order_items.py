"""merge branches: messages + order_items

Revision ID: 871653bfd1ed
Revises: 3e5c_add_messages, 4b2c4b3b8f9a
Create Date: 2025-08-18 02:31:42.913085
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '871653bfd1ed'
down_revision = ('3e5c_add_messages', '4b2c4b3b8f9a')
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass