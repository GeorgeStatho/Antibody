from google.adk.agents.llm_agent import Agent

root_agent = Agent(
    model='<FILL_IN_MODEL>',
    name='',
    description='The start point of utilizing the agent team',
    instruction='When awoken, call the Triage Agent to determine the severity of the error',
)
