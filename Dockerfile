FROM python:3.11-slim

WORKDIR /app`r`nWORKDIR /app/backend

RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY backend ./backend

RUN pip install -r backend/requirements.txt

ENV PYTHONUNBUFFERED 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "]
