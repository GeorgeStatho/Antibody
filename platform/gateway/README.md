# Agent Gateway

Unified entry point for the fleet: routing and policy enforcement in front of every agent.

**Status:** not implemented.

Every untrusted-text ingest passes through Model Armor *here*, before it reaches a
model — alert payloads and log bodies are attacker-reachable surface.

## To build (Phase 2, Day 8)

- [ ] Route incoming incident events to the correct agent
- [ ] Model Armor inline on the ingest path
- [ ] Emit a trace span for every block event (this is the demo artifact)
- [ ] Reject-and-log on block; never pass sanitized-but-suspect text through silently
