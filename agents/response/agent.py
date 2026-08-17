"""Response agent — rollback proposal, human approval gate, verification.

Identity scope: write, gated. The write identity stays locked until a human approves.
Build target: Phase 1, Day 5.
"""

from google.adk.agents.llm_agent import Agent

from agents.common import config

# TODO(day5): propose a Cloud Run revision rollback with an explicit blast radius.
# TODO(day5): human approval gate — publish to the approvals topic, block on the reply.
# TODO(day5): post-rollback healthcheck. On failure, ESCALATE. Never retry blindly.
root_agent = Agent(
    model=config.MODEL_ID,
    name="response_agent",
    description="Proposes a gated rollback, waits for human approval, executes and verifies it.",
    instruction="STUB — not yet implemented.",
)
