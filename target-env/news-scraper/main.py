"""news-scraper — emits fake articles onto the raw-articles topic.

STUB. See ../README.md for the requirements this has to meet.
"""

from fastapi import FastAPI

app = FastAPI()


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "news-scraper"}


# TODO(day1): publish a synthetic article to TOPIC_RAW_ARTICLES on a timer or
# on POST /tick. Structured JSON log per publish.
