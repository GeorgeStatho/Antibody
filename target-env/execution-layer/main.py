"""execution-layer — mock broker. Writes positions to Firestore, nothing else.

STUB. See ../README.md for the requirements this has to meet.

There is no live broker integration here and there never will be. No API keys,
no order routing, no credentials.
"""

from fastapi import FastAPI

app = FastAPI()


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "execution-layer"}


# TODO(day1): consume signals, write a position document to Firestore.
