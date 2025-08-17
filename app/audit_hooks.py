"""
SQLAlchemy event listeners to ensure audit_logs.order_code is populated.
This prevents NOT NULL violations when only order_id is provided.
"""

from sqlalchemy import event, text

# Import models; adjust this import if your models live elsewhere.
from .models import AuditLog  # expects app/models.py defining class AuditLog

@event.listens_for(AuditLog, "before_insert")
def set_order_code_before_insert(mapper, connection, target):
    """
    If an AuditLog is being inserted with order_id but without order_code,
    look up orders.code from the DB and set it on the row before insert.
    """
    # If already present or no order_id, do nothing
    if getattr(target, "order_code", None) or not getattr(target, "order_id", None):
        return

    code = connection.execute(
        text("SELECT code FROM orders WHERE id = :oid"),
        {"oid": target.order_id},
    ).scalar()

    if code:
        target.order_code = code
