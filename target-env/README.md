# Target Environment — the patient

`news-scraper → Pub/Sub(raw-articles) → llm-classifier → Pub/Sub(signals) → execution-layer → Firestore`

## What this is, and what it is not

This is a **purpose-built fake**, not a port of the real trading stack.

The target environment's only job is to be a realistic failure surface: emit
structured logs, carry trace context, and break on demand. Nothing a judge sees
depends on the trading logic being real. Porting the actual docker-compose
monolith would cost days and buy zero demo value — days that Phase 1 Day 6
(Memory Bank) and Phase 2 Days 8–9 (injection block, MTTR delta) need.

**No broker credentials exist anywhere in this tree.** The executor writes to
Firestore and nothing else. Do not copy a service-account key file in here.

## Requirements each service must meet

These are the only things that matter — the fleet reads them, so they are load-bearing:

- [ ] Structured JSON logs to Cloud Logging (severity + a stable `service` field)
- [ ] OpenTelemetry trace context propagated across the Pub/Sub hops
- [ ] A `/healthz` endpoint the Response agent can probe post-rollback
- [ ] A deliberate, injectable failure mode in `llm-classifier` (see `demo/inject-failure.py`)
- [ ] Deployed as distinct Cloud Run revisions, so there is something to roll *back to*

## Build target

Phase 0, Day 1. Aim for ~50 lines per service. If one grows past that, it is
doing work the demo does not need.
