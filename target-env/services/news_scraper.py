"""news-scraper — emits synthetic articles onto the raw-articles topic.

No timer inside the process: Cloud Run scales to zero, so ticking is Cloud
Scheduler's job for ambient traffic and demo/inject-failure.py's job for the burst
that drives the error rate over threshold while a camera is running.
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI

from pipeline.domain import Article
from pipeline.messaging import MessagePublisher
from pipeline.telemetry import StructuredLogger
from pipeline.tracing import TraceContext
from pipeline.wiring import build_logger, build_publisher

SERVICE_NAME = "news-scraper"

HEADLINES = (
    ("ACME", "ACME beats earnings expectations"),
    ("ACME", "ACME recalls flagship product"),
    ("ZENITH", "Zenith announces record buyback"),
    ("ZENITH", "Zenith cuts full-year guidance"),
)


class ArticleSource:
    """Produces one synthetic article per tick."""

    def next_article(self) -> Article:
        ticker, headline = HEADLINES[uuid.uuid4().int % len(HEADLINES)]
        return Article(article_id=str(uuid.uuid4()), headline=headline, ticker=ticker)


class Scraper:
    def __init__(self, source: ArticleSource, publisher: MessagePublisher,
                 logger: StructuredLogger) -> None:
        self._source = source
        self._publisher = publisher
        self._logger = logger

    def tick(self) -> Article:
        article = self._source.next_article()
        trace = TraceContext.new()
        self._publisher.publish(article.as_dict(), trace)
        self._logger.info("article_published", trace=trace, article_id=article.article_id,
                          ticker=article.ticker)
        return article


def build_scraper() -> Scraper:
    return Scraper(
        ArticleSource(),
        build_publisher("TOPIC_RAW_ARTICLES"),
        build_logger(SERVICE_NAME),
    )


def app_factory() -> FastAPI:
    """Built on demand, not at import. `uvicorn ... --factory` calls this.

    Importing a service module must not require a project, a client, or a network:
    otherwise the module cannot be read by a test, and the composition it performs
    is invisible until it fails at startup.
    """
    app = FastAPI(title=SERVICE_NAME)
    scraper = build_scraper()

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "service": SERVICE_NAME}

    @app.post("/tick")
    def tick():
        return {"article_id": scraper.tick().article_id}

    return app
