# Order Intake Suite – Backend

FastAPI-based backend for parsing WhatsApp messages into orders, tracking rentals/instalments, payments,
documents (invoice/receipt/instalment agreement), adjustments (return, instalment cancel, buyback), and Excel export (cash basis).

## Quick start (Windows-friendly)

1) Install Python 3.11+ and Git.
2) `cd backend`
3) `python -m venv .venv && .venv\Scripts\activate`
4) `pip install -r requirements.txt`
5) Copy `.env.example` to `.env` and fill in values (especially `OPENAI_API_KEY`). For local dev, you may use SQLite (default).
6) Run: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
7) Open http://localhost:8000/docs

## Deployment (Render + Postgres)

- Create a Render Web Service for this folder with Docker or `render.yaml`.
- Add environment variables (OPENAI_API_KEY, DATABASE_URL, CORS_ORIGINS, OPENAI_MODEL).
- Use a Render Postgres instance and set `DATABASE_URL` accordingly.
- Alembic migrations are included; run them via `alembic upgrade head` or let `app.main` auto-create tables (dev only).

## Key Design Notes

- **Structured parsing**: Uses OpenAI (default: `gpt-4o-mini`) with a strict JSON Schema.
- **No-prorate rules**: Rentals charge by full months (recurring, accumulates). Instalments are fixed months, no prorate.
- **Adjustments (Option B)**: Never modify original invoices. Create child adjustment orders with code suffixes:
  - `-R` for rental return/collect
  - `-I` for instalment cancel
  - `-B` for buyback
- **Cash-basis export**: `/export/cash.xlsx?start=YYYY-MM-DD&end=YYYY-MM-DD` includes non-void payments only.
- **PDFs**: Simple but clean PDFs via ReportLab for invoice, receipt, instalment agreement.
- **Product mapping**: RapidFuzz-based alias matching for SKUs (Malay/English mixed terms supported).

