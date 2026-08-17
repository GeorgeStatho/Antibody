"""Memory agent — extracts and persists the incident signature.

Identity scope: write to Memory Bank only.
Build target: Phase 1, Day 6. This is the load-bearing piece — protect this day.
"""

from google.adk.agents.llm_agent import Agent

from agents.common import config

# TODO(day6): write {symptom_fingerprint, root_cause, fix_applied, timestamp}.
# The fingerprint has to be matchable by Diagnosis on the next occurrence —
# design the key shape before writing the extraction prompt.
root_agent = Agent(
    model=config.MODEL_ID,
    name="memory_agent",
    description="Extracts an incident signature and persists it to the Memory Bank.",
    instruction="STUB — not yet implemented.",
)
