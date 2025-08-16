from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

router = APIRouter(prefix="/metrics")

PARSE_LATENCY = Histogram("orderops_parse_latency_seconds", "Latency for parse operations")
MATCH_HIT = Counter("orderops_match_hit_total", "Count of order match hits", ["reason"])
ACCRUAL_CREATED = Counter("orderops_accrual_entries_created_total", "Count of new accrual ledger entries created")

@router.get("")
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
