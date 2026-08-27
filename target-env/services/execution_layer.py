"""execution-layer — mock broker. Writes positions to Firestore and nothing else.

There is no live broker integration here and there never will be. No API keys, no
order routing, no credentials.

Positions are keyed by the Pub/Sub message id, so at-least-once delivery records
one position rather than counting the same signal twice.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pipeline.domain import Position, Signal
from pipeline.telemetry import StructuredLogger
from pipeline.web import create_app
from pipeline.wiring import build_logger, build_positions_collection

SERVICE_NAME = "execution-layer"


class PositionBook:
    """Writes positions. The Firestore collection is injected."""

    def __init__(self, collection) -> None:
        self._collection = collection

    def record(self, position: Position) -> None:
        self._collection.document(position.message_id).set(position.as_dict())


class Executor:
    def __init__(self, book: PositionBook, logger: StructuredLogger) -> None:
        self._book = book
        self._logger = logger

    def handle(self, message) -> None:
        signal = Signal.from_dict(message.payload)
        position = Position(signal=signal, message_id=message.message_id,
                            written_at=self._now())
        self._book.record(position)
        self._logger.info("position_written", trace=message.trace,
                          article_id=signal.article_id, ticker=signal.ticker,
                          action=signal.action)

    def _now(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def build_executor() -> Executor:
    return Executor(PositionBook(build_positions_collection()), build_logger(SERVICE_NAME))


def app_factory():
    """Built on demand, not at import. `uvicorn ... --factory` calls this."""
    return create_app(SERVICE_NAME, build_executor(), build_logger(SERVICE_NAME))
