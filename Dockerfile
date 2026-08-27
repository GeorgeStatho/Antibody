# One image for the whole fleet. FLEET_AGENT selects which agent it serves, so a
# change to the HTTP layer or the shared libraries lands on all four at once
# rather than drifting between four near-identical Dockerfiles.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    FLEET_AGENT=triage

WORKDIR /app

# Dependencies first, so editing agent code does not reinstall them.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY agents/ ./agents/

# Cloud Run assigns $PORT and may change it between revisions, so it is read at
# start rather than baked in. `exec` keeps uvicorn as PID 1 and lets it receive
# the shutdown signal directly.
CMD exec uvicorn "agents.${FLEET_AGENT}.main:app" --host 0.0.0.0 --port "${PORT}"
