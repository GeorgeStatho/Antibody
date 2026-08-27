"""Model Armor — the guardrail on every untrusted-text ingest.

Whether a scanner is available is settled once, at composition time, by choosing an
implementation. Nothing downstream asks whether a template was configured; it asks
a scanner to scan and reads the verdict.

WARNING. A scan that fails is not a pass. Every implementation here reports
scanned=False on any doubt, and ArmorVerdict.is_clean is false in that state, so
untrusted text never reaches a model on the strength of a guardrail that did not
run.
"""

from __future__ import annotations

import logging
from typing import Protocol

from agents.common.schemas import ArmorVerdict
from agents.common.values import UntrustedText

logger = logging.getLogger(__name__)

MATCH_FOUND = "MATCH_FOUND"
REGIONAL_ENDPOINT = "modelarmor.{location}.rep.googleapis.com"
TEMPLATE_PATH = "projects/{project}/locations/{location}/templates/{template}"


class TextScanner(Protocol):
    """Scans attacker-reachable text before it can become prompt content."""

    def scan(self, text: UntrustedText) -> ArmorVerdict: ...


class UnconfiguredScanner:
    """Stands in when no Model Armor template exists.

    Reports every scan as unperformed, which leaves Triage classifying from trusted
    metrics alone. It logs on every call because an agent quietly running without
    its guardrail is exactly the state this project claims never to be in.
    """

    REASON = "template_not_configured"

    def scan(self, text: UntrustedText) -> ArmorVerdict:
        logger.warning(
            "No Model Armor template configured. Untrusted alert text is not being "
            "scanned and will be withheld from the model."
        )
        return ArmorVerdict(scanned=False, blocked=False, skipped_reason=self.REASON)


class ModelArmorScanner:
    """Scans text against a configured Model Armor template."""

    def __init__(self, client, template: str) -> None:
        self._client = client
        self._template = template

    def scan(self, text: UntrustedText) -> ArmorVerdict:
        if text.is_empty:
            return ArmorVerdict(scanned=True, blocked=False)
        try:
            return self._verdict_for(text)
        except Exception as error:  # noqa: BLE001 - a guardrail outage must not eat the alert
            logger.exception("Model Armor scan failed; treating the text as unscanned")
            return ArmorVerdict(
                scanned=False,
                blocked=False,
                skipped_reason=f"scan_error: {type(error).__name__}",
            )

    def _verdict_for(self, text: UntrustedText) -> ArmorVerdict:
        from google.cloud import modelarmor_v1

        response = self._client.sanitize_user_prompt(
            request=modelarmor_v1.SanitizeUserPromptRequest(
                name=self._template,
                user_prompt_data=modelarmor_v1.DataItem(text=text.content),
            )
        )
        result = response.sanitization_result
        return ArmorVerdict(
            scanned=True,
            blocked=MATCH_FOUND in str(result.filter_match_state),
            findings=self._findings(result),
        )

    def _findings(self, result) -> list[str]:
        matched = [
            name
            for name, outcome in (result.filter_results or {}).items()
            if MATCH_FOUND in str(outcome)
        ]
        return sorted(matched)


def build_template_path(template: str, project: str, location: str) -> str:
    """Accepts a bare template id or an already-qualified resource path."""
    if template.startswith("projects/"):
        return template
    return TEMPLATE_PATH.format(project=project, location=location, template=template)


def build_regional_client(location: str):
    from google.api_core.client_options import ClientOptions
    from google.cloud import modelarmor_v1

    endpoint = REGIONAL_ENDPOINT.format(location=location)
    return modelarmor_v1.ModelArmorClient(client_options=ClientOptions(api_endpoint=endpoint))


class ModelBoundaryGuard:
    """The last checkpoint before a prompt reaches Vertex.

    Installed as an ADK before_model_callback. It duplicates the scan Triage already
    performs, deliberately: that one is a call a future code path can forget to make,
    and this one sits on the only route to the model.
    """

    def __init__(self, scanner: TextScanner) -> None:
        self._scanner = scanner

    def __call__(self, callback_context, llm_request):
        prompt = self._prompt_text(llm_request)
        if prompt.is_empty:
            return None

        verdict = self._scanner.scan(prompt)
        if not verdict.blocked:
            return None

        logger.warning("Model Armor blocked a prompt at the model boundary: %s", verdict.findings)
        return self._refusal(verdict)

    def _prompt_text(self, llm_request) -> UntrustedText:
        fragments = [
            part.text
            for content in getattr(llm_request, "contents", None) or []
            for part in getattr(content, "parts", None) or []
            if getattr(part, "text", None)
        ]
        return UntrustedText("\n".join(fragments))

    def _refusal(self, verdict: ArmorVerdict):
        from google.adk.models.llm_response import LlmResponse
        from google.genai import types

        matched = ", ".join(verdict.findings) or "a guardrail filter"
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"{BLOCKED_MARKER}: the alert text matched {matched}.")],
            )
        )


BLOCKED_MARKER = "BLOCKED_BY_MODEL_ARMOR"
