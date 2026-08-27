"""llm-classifier — turns articles into signals. This is the service that breaks.

There is no model here on purpose. A real one would add a second failure surface,
cost quota on every demo run, and change nothing a judge sees. The classification
is a lookup; the interesting behaviour is the injectable failure.
"""

from __future__ import annotations

import os

from pipeline.domain import BUY, HOLD, SELL, Article, Signal
from pipeline.failure import INJECTED_FAILURE, FailurePolicy, InjectedFailure, select_failure_policy
from pipeline.messaging import MessagePublisher
from pipeline.telemetry import StructuredLogger
from pipeline.web import create_app
from pipeline.wiring import build_logger, build_publisher

SERVICE_NAME = "llm-classifier"

CONFIDENT = 0.9
UNCERTAIN = 0.5

POSITIVE_WORDS = ("beats", "record", "surges", "raises")
NEGATIVE_WORDS = ("recalls", "cuts", "misses", "falls")


class SentimentTable:
    """A lookup, not a model."""

    def action_for(self, headline: str) -> tuple[str, float]:
        words = headline.lower()
        if any(word in words for word in POSITIVE_WORDS):
            return BUY, CONFIDENT
        if any(word in words for word in NEGATIVE_WORDS):
            return SELL, CONFIDENT
        return HOLD, UNCERTAIN


class Classifier:
    def __init__(self, table: SentimentTable, failure: FailurePolicy,
                 publisher: MessagePublisher, logger: StructuredLogger) -> None:
        self._table = table
        self._failure = failure
        self._publisher = publisher
        self._logger = logger

    def handle(self, message) -> None:
        article = Article.from_dict(message.payload)
        if self._failure.should_fail():
            self._logger.error("classify_failed", error_class=INJECTED_FAILURE,
                               trace=message.trace, article_id=article.article_id)
            raise InjectedFailure(article.article_id)

        signal = self._classify(article)
        self._publisher.publish(signal.as_dict(), message.trace)
        self._logger.info("signal_published", trace=message.trace,
                          article_id=article.article_id, action=signal.action)

    def _classify(self, article: Article) -> Signal:
        action, confidence = self._table.action_for(article.headline)
        return Signal(article_id=article.article_id, ticker=article.ticker,
                      action=action, confidence=confidence)


def build_classifier() -> Classifier:
    return Classifier(
        SentimentTable(),
        select_failure_policy(os.environ),
        build_publisher("TOPIC_SIGNALS"),
        build_logger(SERVICE_NAME),
    )


def app_factory():
    """Built on demand, not at import. `uvicorn ... --factory` calls this."""
    return create_app(SERVICE_NAME, build_classifier(), build_logger(SERVICE_NAME))
