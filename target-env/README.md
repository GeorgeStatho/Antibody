# Target Environment — the patient

`news-scraper → Pub/Sub(raw-articles) → llm-classifier → Pub/Sub(signals) → execution-layer → Firestore`

Build plan and open work: [PLAN.md](PLAN.md).

## What this is, and what it is not

This is a **purpose-built fake**, not a port of the real trading stack.

Its only job is to be a realistic failure surface: emit structured logs, carry trace
context, and break on demand. Nothing a judge sees depends on the trading logic
being real. Porting the actual monolith would cost days and buy zero demo value.

**No broker credentials exist anywhere in this tree.** The executor writes to
Firestore and nothing else. Do not copy a service-account key file in here.

## Layout

```
pipeline/     shared, and the reason there is one image rather than three
  domain.py     Article, Signal, Position
  telemetry.py  the log schema the fleet reads
  tracing.py    W3C trace context across the Pub/Sub hops
  messaging.py  push envelope in, published message out
  failure.py    the injectable failure mode
  web.py        healthcheck + push route
  wiring.py     environment -> collaborators, read in one place
services/
  news_scraper.py llm_classifier.py execution_layer.py
tests/        no GCP anywhere in the test path
Dockerfile    one image; TARGET_MODULE selects the service
```

**One image, three services.** All three share the log schema, the trace
propagation and the envelope handling, and those are exactly the pieces the agent
fleet reads. Three near-identical images would let that contract drift service by
service, and a drifted log schema silently breaks the symptom fingerprint that the
Memory Bank matches on.

## Requirements each service must meet

The fleet reads these, so they are load-bearing:

- [x] Structured JSON logs (severity, and a stable `service` and `event`)
- [x] OpenTelemetry trace context propagated across the Pub/Sub hops
- [x] A `/healthz` endpoint the Response agent can probe post-rollback
- [x] A deliberate, injectable failure mode in `llm-classifier`
- [ ] Deployed as distinct Cloud Run revisions, so there is something to roll *back* to

The last one is true by construction — `demo/inject-failure.py` injects the failure
as an env-var change, which mints a new revision — but it is unchecked because
nothing has been deployed yet.

## Running the tests

```bash
cd target-env && python -m pytest
```

Nothing in the suite touches GCP; every client is injected.
