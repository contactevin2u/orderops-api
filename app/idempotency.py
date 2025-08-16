from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from .db import SessionLocal
from .models import IdempotencyKey

class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key = request.headers.get("Idempotency-Key")
        if request.method in ("POST", "PUT", "PATCH") and key:
            db = SessionLocal()
            try:
                existing = db.query(IdempotencyKey).filter(IdempotencyKey.key == key).first()
                if existing:
                    return JSONResponse({"detail": "Duplicate request"}, status_code=409)
                entry = IdempotencyKey(key=key, method=request.method, path=str(request.url))
                db.add(entry)
                db.commit()
            finally:
                db.close()
        response = await call_next(request)
        return response
