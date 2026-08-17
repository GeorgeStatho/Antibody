"""llm-classifier — turns articles into signals. This is the service that breaks.

STUB. See ../README.md for the requirements this has to meet.
"""

from fastapi import FastAPI

app = FastAPI()


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "llm-classifier"}


# TODO(day1): consume raw-articles (push subscription), classify, publish to signals.
# TODO(day1): the injectable failure mode — an env var or a bad revision that drives
# the error rate from ~0% to ~30%+ within seconds. `demo/inject-failure.py` flips it.
# Whatever the mechanism, it must be visible in Cloud Logging as an error-rate spike,
# because that spike is what the Cloud Monitoring alert policy fires on.
