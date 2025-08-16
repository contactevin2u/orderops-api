import io, csv
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from .models import Order, OrderItem, Event, Payment, LedgerEntry, OrderStatus

def _date(obj):
    return obj.isoformat() if hasattr(obj, "isoformat") else (obj or "")

def _parse_dt(s: str | None):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

def build_export_csv(db: Session, start: str | None = None, end: str | None = None,
                     include_children: bool = True, include_adjustments: bool = True,
                     only_unsettled: bool = False) -> str:
    q = db.query(Order).options(joinedload(Order.customer))
    dt_start = _parse_dt(start)
    dt_end = _parse_dt(end)
    if dt_start:
        q = q.filter(Order.created_at >= dt_start)
    if dt_end:
        # include the entire end day
        q = q.filter(Order.created_at < (dt_end + timedelta(days=1)))
    if only_unsettled:
        q = q.filter(Order.status == OrderStatus.CONFIRMED)
    orders = q.order_by(Order.id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["OrderCode", "ExternalID", "Type", "Status", "CustomerName", "Phone", "DueDate",
                     "ReturnDue", "CreatedDate", "ReturnedDate", "CollectedDate", "Notes", "ParentOrder",
                     "Outstanding"])

    for o in orders:
        if not include_children and o.parent_id:
            continue
        initial = sum(float(l.amount) for l in o.ledger if l.kind.name == "INITIAL_CHARGE")
        monthly = sum(float(l.amount) for l in o.ledger if l.kind.name == "MONTHLY_CHARGE")
        paid = sum(float(p.amount) for p in o.payments)
        outstanding = initial + monthly - paid
        writer.writerow([
            o.order_code, o.external_id or "", o.type.name if hasattr(o.type, "name") else str(o.type),
            o.status.name if hasattr(o.status, "name") else str(o.status),
            o.customer.name if o.customer else "", o.customer.phone if o.customer else "",
            _date(o.due_date), _date(o.return_due_date), _date(o.created_at), _date(o.returned_at),
            _date(o.collected_at), o.notes or "", "", f"{outstanding:.2f}"
        ])
        if include_adjustments:
            for l in o.ledger:
                if l.kind.name == "ADJUSTMENT":
                    writer.writerow([f"{o.order_code}-ADJ", "", "", "ADJUSTMENT", "", "", "", l.period or "",
                                     "", "", "", l.note or "", o.order_code, f"{float(l.amount):.2f}"])
    return output.getvalue()
