"""Where configuration turns into collaborators.

Configuration is read here and nowhere below. Everything downstream receives what
it needs through its constructor, so a test can substitute a stub without setting
an environment variable and a deployment cannot silently construct a half-wired
component.
"""

from __future__ import annotations

from agents.common import config
from agents.common.armor import (
    ModelArmorScanner,
    TextScanner,
    UnconfiguredScanner,
    build_regional_client,
    build_template_path,
)


def build_scanner() -> TextScanner:
    """Chooses the scanner once, from configuration.

    Callers ask a scanner to scan; none of them asks whether a template exists.
    """
    template = (config.MODEL_ARMOR_TEMPLATE_ID or "").strip()
    if not template:
        return UnconfiguredScanner()

    return ModelArmorScanner(
        client=build_regional_client(config.REGION),
        template=build_template_path(template, config.PROJECT_ID, config.REGION),
    )
