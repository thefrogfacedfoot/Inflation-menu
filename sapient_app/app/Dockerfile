# Finder service. Build context is the REPO ROOT (see ops/docker-compose.yml)
# so we can copy ops/logging/python in alongside the app/ package.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/ops/logging/python

WORKDIR /app

# System deps for psycopg + healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

# App package and shared observability lib.
COPY app /app/app
COPY ops/logging/python /app/ops/logging/python
COPY run.py /app/run.py

EXPOSE 8000 9090

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
