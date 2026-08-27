# Status — Triage and the Target Environment Run; the Rest Is Stubs

**As of:** Wed Aug 26 2026, ~22:45 EDT
**Deadline:** Mon Aug 31, 5:00pm PDT

This document records exactly what exists, what has been verified, and what remains.
It is deliberately pessimistic: **nothing is marked done unless it has been run.**
Companion to [build-order.md](build-order.md), which holds the schedule, and to the
two build plans — [agents/triage/PLAN.md](agents/triage/PLAN.md) and
[target-env/PLAN.md](target-env/PLAN.md).

---

## Current state in one line

The target environment is **deployed and processing messages end to end on GCP**,
and the Triage agent is **built, tested, and answering from Vertex** — but it is not
deployed, no alert policy exists, and Diagnosis, Response and Memory are still the
original stubs.

---

## What runs

### Verified against real infrastructure

| Claim | How it was verified |
|---|---|
| An article flows scraper → classifier → executor → Firestore | Published to `raw-articles`; `signal_published` and `position_written` logged; the position document exists |
| One trace spans the Pub/Sub hops | Both services logged trace id `fb020c1d…` with distinct span ids |
| Positions are not double-counted | Keyed by Pub/Sub `messageId`; unit-proven, and one document per delivery in Firestore |
| Triage answers from Vertex | `PYTHONPATH=. adk run agents/triage` returned a valid `Decision`: sev2, page, correct rationale |
| `bootstrap.sh` is idempotent | Ran twice; second run reported every resource as existing |
| Identity split is real | Four service accounts created; `sa-diagnosis` holds no write role |

### Deployed on GCP

| Resource | State |
|---|---|
| Cloud Run: `news-scraper`, `llm-classifier`, `execution-layer` | deployed, revision 00001, serving |
| Pub/Sub topics | `raw-articles`, `signals`, `incidents`, `triage-verdicts`, `approvals`, `dead-letter` |
| Push subscriptions | `raw-articles-to-classifier`, `signals-to-executor`, both with a dead-letter topic and capped retries |
| Firestore | database `firebase`, `us-central1`, native; `positions` collection populated |
| Log-based metric | `classifier_errors`, filtering `jsonPayload.event="classify_failed"` |
| Service accounts | `sa-triage`, `sa-diagnosis`, `sa-response`, `sa-memory`, all bound |

### Code

| Area | State |
|---|---|
| `agents/common/` | values, alert parsing, fingerprint, schemas, armor, errors, tracing, serve, wiring |
| `agents/triage/` | rules, classifier, ledger, publisher, service, factory, agent, main |
| `target-env/pipeline/` | domain, telemetry, tracing, messaging, failure, web, wiring |
| `target-env/services/` | `news_scraper`, `llm_classifier`, `execution_layer` |
| Tests | **94 fleet + 45 target-env, all passing.** No GCP client anywhere in either test path |
| `Dockerfile` ×2 | one per plane; `FLEET_AGENT` / `TARGET_MODULE` selects the service. **Neither has been `docker build`-ed — no daemon available here** |

The code follows [CleanCode.md](CleanCode.md): collaborators are injected, the
severity rubric is one class per rule rather than a conditional cascade, and each
test carries a single assertion.

---

## What does NOT run

| Component | State |
|---|---|
| `agents/diagnosis`, `agents/response`, `agents/memory` | **still `instruction="STUB — not yet implemented."`** |
| `infra/setup-monitoring.sh` | still `exit 1`. No alert policy, no notification channel, no subscription to `incidents` |
| `infra/deploy-fleet.sh` | runnable and deploys only `triage`, but **has never been run** |
| Model Armor | `MODEL_ARMOR_TEMPLATE_ID` is empty. Triage runs `UnconfiguredScanner`, which reports every scan as unperformed |
| `demo/poisoned-log.py`, `demo/mttr-report.py` | still `raise SystemExit("not implemented")` |
| `demo/inject-failure.py` | written, but **blocked** — see the open issue below |
| Memory Bank | nothing writes it. `triage-verdicts` is Triage's own ledger, not the Memory Bank |
| `platform/registry/agents.yaml` | all seven still read `registered / not implemented`. Triage is close but is not deployed or alert-wired, so the status stays |

---

## Open issue — blocking

**The `run.app` URLs are unreachable from the dev machine.** Every target service
returns Google's generic unknown-host 404 over IPv4 and IPv6, authenticated and not.

It is not the containers: uvicorn logs `Application startup complete`, the startup
TCP probe passes, and **no request ever reaches the container**. It is not the
config: ingress is `all`, `allUsers` holds `run.invoker`, traffic is 100% to the
ready revision. The 404 carries no `server` header — Google's unknown-host page —
while `cloud.google.com` from the same shell returns `server: ESF`.

Pub/Sub push is unaffected because it originates inside Google's network, which is
why the pipeline runs end to end regardless.

**What it blocks:** `demo/inject-failure.py` drives its traffic burst by ticking the
scraper over its public URL. The fallback is publishing to `raw-articles` directly,
which is what the pipeline verification already does. Not yet diagnosed further;
installing the `cloud-run-proxy` gcloud component would isolate it.

---

## Corrections to earlier versions of this document

Recorded because each was believed and was wrong.

1. **"Get one agent answering locally via `adk run agents/triage`" was not
   achievable as written.** ADK's loader puts `agents/` on `sys.path` and imports
   the package as `triage`, so `from agents.common import config` cannot resolve.
   `PYTHONPATH=.` is required, and is now documented in the README.
2. **The Firestore checkbox was stale.** The database already existed, named
   `firebase`. The real defect was that the Triage ledger built its client without
   `database=`, so it pointed at `(default)`, which does not exist in this project.
3. **`VERTEX_MODEL_ID` was set to a model that does not exist.** It read
   `publishers/google/models/gemini-3.5-flash`. Verified against Vertex in
   `us-central1`: `gemini-2.5-flash` responds; `gemini-2.0-flash`, `gemini-3-flash`
   and `gemini-flash-latest` all 404. ADK also wants the bare id, not a resource path.
4. **`google-adk` was never installed** in the Python that was being used. It is
   present in the `AntiBody` conda environment, version 2.7.0.
5. **The YAML files had never been parsed.** They parse.

---

## Open decisions

**The approval gate mechanism (needed before Response).** `sa-response` holds
`roles/run.developer` as a standing grant, so it can write to prod at rest — the
opposite of the README's claim. Three candidates, still none chosen: a conditional
IAM binding, a short-lived token minted after approval, or a separate privileged SA
impersonated only post-approval.

**Agent naming is still inconsistent.** README and all code say **Response** and
**Memory**; `build-order.md` and `docs/architecture.mermaid` say **Remediation** and
**Postmortem**. The diagram appears in the demo video. Reconcile before wiring
Response and Memory, because their routing constants bake the names in.

**Memory Bank storage backend.** `config.py` and `iam.yaml` assume a Firestore
collection (`incident-signatures`) with `datastore.*` roles. If Vertex AI Agent
Engine Memory Bank is meant instead, the IAM roles are wrong.

**The root agent — partially resolved.** `agent.py` at the repo root raised on
import (`name=''`, `model='<FILL_IN_MODEL>'`), which broke test collection for the
whole repo, so both literals were repaired. Its instruction had already been edited
to *"call the Triage Agent"*, so it is no longer untouched `adk create` scaffolding.
Whether it becomes the Gateway entry point is still undecided.

---

## What needs to be finished

Ordered by dependency. Days refer to [build-order.md](build-order.md).

### Next — close the Phase 0 Day 3 gate

- [ ] Alert policy JSON in `infra/`, **log-based** so the poisoned log body reaches
      the notification payload — the injection demo is hollow without that
- [ ] Pub/Sub notification channel on `incidents`
- [ ] Triage push-subscribed to `incidents`; remove the `exit 1` from `setup-monitoring.sh`
- [ ] Run `deploy-fleet.sh`; verify `triage-agent` serves
- [ ] Capture a **real** alert notification to `infra/fixtures/alert-open.captured.json`
      and diff it against the synthetic fixtures. Where they disagree, the real one wins
- [ ] Verify the denial: impersonate `sa-diagnosis`, attempt a Cloud Run update,
      confirm `PERMISSION_DENIED`

### Days 4–7 — the spine

- [ ] Diagnosis: memory lookup at the top of the flow, then log/trace/revision
      correlation into a structured hypothesis
- [ ] Response: rollback proposal with blast radius, approval gate, post-rollback
      healthcheck that **escalates rather than retries**
- [ ] Memory: signature persistence. The fingerprint schema is already settled and
      lives in `agents/common/fingerprint.py` — Memory must use it unchanged
- [ ] Update `agents.yaml` statuses only as each agent genuinely starts working

### Days 8–10 — the set-pieces

- [ ] Model Armor template; set `MODEL_ARMOR_TEMPLATE_ID`. Until then Triage is
      developable but **not guarded**, and every verdict says so via `armor.scanned`
- [ ] `poisoned-log.py`, plus a without-armor control run
- [ ] **Record the block on video the day it works**
- [ ] `mttr-report.py`; confirm run 2 is visibly shorter
- [ ] OTel spans exported to Cloud Trace (instrumentation is in place, export is not verified)
- [ ] Export the architecture diagram to PNG

### Days 11–14 — ship

- [ ] Freeze Day 11; video Day 12; write-up Day 13; **submit Sat Aug 30**
- [ ] Fill in the README's "Findings and learnings"
- [ ] Every `status:` in `agents.yaml` set to the truth as of submission

---

## Standing risk, restated

The Memory Bank is still load-bearing and still unbuilt. The fingerprint it depends
on is designed, implemented and pinned by a golden-value test, which removes the
riskiest part — but nothing writes a signature yet, and until something does, the
"weeks of async context" claim is unsupported. The MTTR delta and the injection
block remain the entire differentiation.
