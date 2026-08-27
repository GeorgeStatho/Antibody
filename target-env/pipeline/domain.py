"""What moves through the pipeline.

Dedicated types rather than loose dictionaries, so a signal cannot be published
where an article is expected and a missing field fails where it is written rather
than three hops downstream.
"""

from __future__ import annotations

from dataclasses import dataclass

BUY = "buy"
SELL = "sell"
HOLD = "hold"


@dataclass(frozen=True)
class Article:
    article_id: str
    headline: str
    ticker: str

    def as_dict(self) -> dict:
        return {"article_id": self.article_id, "headline": self.headline, "ticker": self.ticker}

    @classmethod
    def from_dict(cls, payload: dict) -> Article:
        return cls(
            article_id=str(payload["article_id"]),
            headline=str(payload["headline"]),
            ticker=str(payload["ticker"]),
        )


@dataclass(frozen=True)
class Signal:
    article_id: str
    ticker: str
    action: str
    confidence: float

    def as_dict(self) -> dict:
        return {
            "article_id": self.article_id,
            "ticker": self.ticker,
            "action": self.action,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> Signal:
        return cls(
            article_id=str(payload["article_id"]),
            ticker=str(payload["ticker"]),
            action=str(payload["action"]),
            confidence=float(payload["confidence"]),
        )


@dataclass(frozen=True)
class Position:
    """What the mock broker records. There is no broker and never will be."""

    signal: Signal
    message_id: str
    written_at: str

    def as_dict(self) -> dict:
        return {**self.signal.as_dict(), "message_id": self.message_id, "written_at": self.written_at}
