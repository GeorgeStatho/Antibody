# One image for the three target services. TARGET_MODULE selects which one it runs.
#
# They share the log schema, the trace propagation and the Pub/Sub envelope
# handling, and those are exactly the pieces the fleet reads. Three near-identical
# images would let that shared contract drift service by service, and a drifted log
# schema silently breaks the symptom fingerprint.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    TARGET_MODULE=news_scraper

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY pipeline/ ./pipeline/
COPY services/ ./services/

# $PORT is read at start because Cloud Run may change it between revisions. `exec`
# keeps uvicorn as PID 1 so it receives the shutdown signal directly.
CMD exec uvicorn "services.${TARGET_MODULE}:app_factory" --factory \
    --host 0.0.0.0 --port "${PORT}"
