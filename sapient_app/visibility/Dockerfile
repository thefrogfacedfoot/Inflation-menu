# Visibility service. Build context is the REPO ROOT (see ops/docker-compose.yml)
# so ops/logging/python is reachable.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/visibility:/app/ops/logging/python

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY visibility/requirements.txt /app/visibility/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/visibility/requirements.txt

COPY visibility /app/visibility
COPY ops/logging/python /app/ops/logging/python

EXPOSE 8001 9092

CMD ["uvicorn", "visibility.api:app", "--host", "0.0.0.0", "--port", "8001", "--app-dir", "/app/visibility"]
