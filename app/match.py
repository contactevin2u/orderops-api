from sqlalchemy.orm import Session
from .models import Order, Customer
from .util import norm_phone

def match_order(db: Session, name: str | None, phone: str | None, external_id: str | None, matcher: str = "hybrid"):
    if external_id:
        order = db.query(Order).filter(Order.external_id == external_id).first()
        if order:
            return {"order_code": order.order_code, "reason": "id"}
    if phone:
        phone_norm = norm_phone(phone)
        customer = db.query(Customer).filter(Customer.phone_norm == phone_norm).first()
        if customer and customer.orders:
            return {"order_code": customer.orders[-1].order_code, "reason": "phone"}
    if name:
        customer = db.query(Customer).filter(Customer.name == name).first()
        if customer and customer.orders:
            return {"order_code": customer.orders[-1].order_code, "reason": "name"}
    return None
