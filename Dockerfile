FROM python:3.11-slim

# System libs for psycopg2
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt

# (Optional but recommended) run DB migrations before starting
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh","-c","alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
