FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG CACHE_BUST=2025-08-18

COPY app ./app
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY scripts ./scripts

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]