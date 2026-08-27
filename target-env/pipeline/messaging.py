"""Pub/Sub in and out, with the trace context carried on the message attributes.

The push envelope arrives shaped the way Pub/Sub sends it, not the way the service
wants it, so the unwrapping lives here rather than in three request handlers.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass

from pipeline.tracing import TraceContext

PUBLISH_TIMEOUT_SECONDS = 30


class MalformedMessage(ValueError):
    """Permanently unusable. The caller acknowledges rather than retrying."""


@dataclass(frozen=True)
class IncomingMessage:
    """One delivered Pub/Sub message, already unwrapped."""

    payload: dict
    message_id: str
    trace: TraceContext


class PushDecoder:
    """Unwraps the Pub/Sub push envelope."""

    def decode(self, body: dict) -> IncomingMessage:
        message = body.get("message")
        if not isinstance(message, dict):
            raise MalformedMessage("push body has no message object")

        return IncomingMessage(
            payload=self._payload_of(message),
            message_id=str(message.get("messageId") or message.get("message_id") or ""),
            trace=TraceContext.from_attributes(message.get("attributes")),
        )

    def _payload_of(self, message: dict) -> dict:
        encoded = message.get("data")
        if not encoded:
            raise MalformedMessage("push message carries no data")
        try:
            payload = json.loads(base64.b64decode(encoded, validate=True))
        except (binascii.Error, ValueError) as error:
            raise MalformedMessage(f"undecodable message data: {error}") from error

        if isinstance(payload, dict):
            return payload
        raise MalformedMessage("message payload is not a JSON object")


class MessagePublisher:
    """Publishes onto one topic. The client and topic path are injected."""

    def __init__(self, client, topic_path: str) -> None:
        self._client = client
        self._topic_path = topic_path

    def publish(self, payload: dict, trace: TraceContext) -> str:
        future = self._client.publish(
            self._topic_path,
            json.dumps(payload).encode("utf-8"),
            **trace.as_attributes(),
        )
        return future.result(timeout=PUBLISH_TIMEOUT_SECONDS)
