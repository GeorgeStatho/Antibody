"""Repo-root agent — `adk create` output, since edited toward a fleet entry point.

OPEN DECISION (STATUS.md): whether this becomes the Agent Gateway entry point or
gets deleted in favour of routing Triage directly off the incidents subscription.
Its instruction has been pointed at Triage, so it is no longer untouched scaffolding.

Repaired here only so the module IMPORTS: `name=''` and `model='<FILL_IN_MODEL>'`
both raised at import time, which broke test collection for the whole repo. The
role question above is untouched and still yours to make.
"""

from google.adk.agents.llm_agent import Agent

from agents.common import config

root_agent = Agent(
    model=config.MODEL_ID,
    name='root_agent',
    description='The start point of utilizing the agent team',
    instruction='When awoken, call the Triage Agent to determine the severity of the error',
)
