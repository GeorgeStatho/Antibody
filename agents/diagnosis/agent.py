"""Diagnosis agent — memory lookup first, then log/trace/deploy correlation.

Identity scope: read-only service account. The write path must be verifiably denied.
Build target: Phase 1, Day 4 (memory lookup step added Day 6).
"""

from google.adk.agents.llm_agent import Agent

from agents.common import config

# TODO(day4): tools for Cloud Logging, Cloud Trace, and Cloud Run revision history.
# TODO(day6): memory lookup step at the TOP of the flow — on a hit, short-circuit
# and emit the stored hypothesis without re-diagnosing. This is the MTTR delta.
root_agent = Agent(
    model=config.MODEL_ID,
    name="diagnosis_agent",
    description="Correlates logs, traces, and recent deploys into a structured root-cause hypothesis.",
    instruction="STUB — not yet implemented.",
)
