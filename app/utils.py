from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from typing import Optional

def months_elapsed_no_prorate(start: datetime, now: Optional[datetime] = None) -> int:
    """Compute whole months elapsed between start and now (no proration).
    If the day-of-month for 'now' is less than the day-of-month for 'start', do not count the current month.
    """
    if not start:
        return 0
    now = now or datetime.now(timezone.utc)
    # Normalize to naive comparison (assuming UTC)
    s = start
    n = now
    months = (n.year - s.year) * 12 + (n.month - s.month)
    if n.day < s.day:
        months -= 1
    return max(months, 0)
