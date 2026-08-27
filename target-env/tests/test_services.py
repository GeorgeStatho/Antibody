"""The three services, against stubs. Nothing here reaches GCP."""

import pytest

from pipeline.domain import BUY, SELL, Article, Signal
from pipeline.failure import FailsAtRate, InjectedFailure, NeverFails
from pipeline.messaging import PushDecoder
from pipeline.tracing import TraceContext
from services.execution_layer import Executor, PositionBook
from services.llm_classifier import Classifier, SentimentTable
from services.news_scraper import ArticleSource, Scraper

ALWAYS_FAILS = FailsAtRate(1.0, chance=lambda: 0.0)

ARTICLE = Article(article_id="a1", headline="ACME beats earnings expectations", ticker="ACME")
SIGNAL = Signal(article_id="a1", ticker="ACME", action=BUY, confidence=0.9)


@pytest.fixture
def deliver(push_message):
    def build(payload, message_id="m1"):
        return PushDecoder().decode(push_message(payload, message_id=message_id))

    return build


def test_a_tick_publishes_one_article(publisher, logger):
    Scraper(ArticleSource(), publisher, logger).tick()
    assert len(publisher.published) == 1


def test_a_tick_logs_the_publication(publisher, logger, logged):
    Scraper(ArticleSource(), publisher, logger).tick()
    assert logged()[0]["event"] == "article_published"


def test_a_published_article_carries_a_trace(publisher, logger):
    Scraper(ArticleSource(), publisher, logger).tick()
    _, trace = publisher.published[0]
    assert len(trace.trace_id) == 32


def test_positive_news_reads_as_a_buy():
    assert SentimentTable().action_for("ACME beats earnings expectations")[0] == BUY


def test_negative_news_reads_as_a_sell():
    assert SentimentTable().action_for("ACME recalls flagship product")[0] == SELL


def test_a_healthy_classifier_publishes_a_signal(publisher, logger, deliver):
    classifier = Classifier(SentimentTable(), NeverFails(), publisher, logger)
    classifier.handle(deliver(ARTICLE.as_dict()))
    assert len(publisher.published) == 1


def test_a_published_signal_carries_the_action(publisher, logger, deliver):
    classifier = Classifier(SentimentTable(), NeverFails(), publisher, logger)
    classifier.handle(deliver(ARTICLE.as_dict()))
    assert publisher.published[0][0]["action"] == BUY


def test_a_signal_keeps_the_incoming_trace(publisher, logger, deliver, push_message):
    trace = TraceContext.new()
    message = PushDecoder().decode(push_message(ARTICLE.as_dict(), trace=trace))
    Classifier(SentimentTable(), NeverFails(), publisher, logger).handle(message)
    assert publisher.published[0][1].trace_id == trace.trace_id


def test_an_injected_failure_raises(publisher, logger, deliver):
    classifier = Classifier(SentimentTable(), ALWAYS_FAILS, publisher, logger)
    with pytest.raises(InjectedFailure):
        classifier.handle(deliver(ARTICLE.as_dict()))


def test_an_injected_failure_publishes_nothing(publisher, logger, deliver):
    classifier = Classifier(SentimentTable(), ALWAYS_FAILS, publisher, logger)
    with pytest.raises(InjectedFailure):
        classifier.handle(deliver(ARTICLE.as_dict()))
    assert publisher.published == []


def test_an_injected_failure_logs_the_event_the_metric_counts(publisher, logger, logged, deliver):
    """`classify_failed` is the log filter behind METRIC_CLASSIFIER_ERRORS."""
    classifier = Classifier(SentimentTable(), ALWAYS_FAILS, publisher, logger)
    with pytest.raises(InjectedFailure):
        classifier.handle(deliver(ARTICLE.as_dict()))
    assert logged()[0]["event"] == "classify_failed"


def test_an_injected_failure_names_its_error_class(publisher, logger, logged, deliver):
    classifier = Classifier(SentimentTable(), ALWAYS_FAILS, publisher, logger)
    with pytest.raises(InjectedFailure):
        classifier.handle(deliver(ARTICLE.as_dict()))
    assert logged()[0]["error_class"] == "injected_failure"


def test_a_signal_becomes_a_position(collection, logger, deliver):
    Executor(PositionBook(collection), logger).handle(deliver(SIGNAL.as_dict()))
    assert len(collection.documents) == 1


def test_a_position_is_keyed_by_the_message_id(collection, logger, deliver):
    Executor(PositionBook(collection), logger).handle(deliver(SIGNAL.as_dict(), message_id="m7"))
    assert "m7" in collection.documents


def test_a_redelivered_signal_writes_one_position(collection, logger, deliver):
    """At-least-once delivery must not count the same signal twice."""
    executor = Executor(PositionBook(collection), logger)
    executor.handle(deliver(SIGNAL.as_dict(), message_id="m7"))
    executor.handle(deliver(SIGNAL.as_dict(), message_id="m7"))
    assert len(collection.documents) == 1


def test_a_position_records_the_action(collection, logger, deliver):
    Executor(PositionBook(collection), logger).handle(deliver(SIGNAL.as_dict()))
    assert collection.documents["m1"]["action"] == BUY
