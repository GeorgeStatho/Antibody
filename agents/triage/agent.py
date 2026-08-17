"""Triage agent — severity classification and the page-a-human decision.

Identity scope: none. Reads the alert payload, nothing else.
Build target: Phase 0, Day 2.
"""

from google.adk.agents.llm_agent import Agent

from agents.common import config

# TODO(day2): real instruction — classify sev1..sev4, auto-close noise,
# decide whether to page. Output a structured verdict, not prose.
root_agent = Agent(
    model=config.MODEL_ID,
    name="triage_agent",
    description="Classifies incident severity and decides whether to page a human.",
    instruction="STUB — not yet implemented.",
)
