FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app
# Do NOT run alembic at build time (no DB). Do it on start.
CMD alembic upgrade head || alembic stamp head; uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
