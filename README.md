# OrderOps API (Rewrite)

- FastAPI, SQLAlchemy (PostgreSQL), idempotent `/v1/orders`.
- Canonical FK: `order_id` only. `order_code` lives only on `orders` for human-friendly code.
- No migrations required for empty DB: tables auto-created on startup.

## Environment
```
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname
OPENAI_API_KEY=sk-...
FRONTEND_ORIGINS=https://your-vercel-app.vercel.app,http://localhost:3000
```
(Use SQLite locally if DATABASE_URL is not set.)

## Run local
```
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Docker (Render)
- Entrypoint runs `create_all` at startup (no Alembic needed since DB is empty).

## Endpoints (prefix `/v1`)
- `POST /v1/orders` (Idempotency-Key header supported)
- `GET  /v1/orders`
- `GET  /v1/orders/{code}`
- `POST /v1/orders/{code}/payments`
- `POST /v1/orders/{code}/event` (RETURN, COLLECT, INSTALMENT_CANCEL, BUYBACK)
- `POST /v1/parse` (LLM strict JSON)
- `GET  /v1/catalog`
- `GET  /v1/reports/aging`
- `GET  /v1/export/xlsx`
- `GET  /v1/calendar`
