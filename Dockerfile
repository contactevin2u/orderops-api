FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
EXPOSE 8000

# Try migrations; if tables exist already, stamp to head; then start API
CMD ["sh","-c","alembic upgrade head || alembic stamp head; uvicorn app.main:app --host 0.0.0.0 --port 8000"]
