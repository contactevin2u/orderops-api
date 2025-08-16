from datetime import datetime
from time import time
from sqlalchemy.orm import Session
from sqlalchemy import text

def next_code(session: Session, prefix: str = "ORD") -> str:
    ym = datetime.now().strftime("%Y%m")
    attempt = 0
    while attempt < 20:
        max_code = session.execute(
            text("SELECT order_code FROM orders WHERE order_code LIKE :like ORDER BY order_code DESC LIMIT 1"),
            {"like": f"{prefix}-{ym}-%"}
        ).scalar()
        seq = int(max_code.rsplit("-", 1)[-1]) + 1 if max_code else 1
        candidate = f"{prefix}-{ym}-{seq:04d}"
        try:
            session.execute(text("INSERT INTO code_reservations(code) VALUES (:c)"), {"c": candidate})
            session.flush()
            return candidate
        except Exception:
            attempt += 1
    return f"{prefix}-{ym}-{int(time()) % 100000:05d}"
