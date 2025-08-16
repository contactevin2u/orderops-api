FROM python:3.11-slim

# psycopg2 build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Run DB migrations, then start API
# If you want strict: remove "|| true" so deploy fails when migrations fail
CMD ["sh","-c","alembic upgrade head || true; uvicorn app.main:app --host 0.0.0.0 --port 8000"]
