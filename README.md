# Antibody

**An agent fleet that gives production systems immune memory.**

First exposure to a failure is slow and expensive. The second should be neither. Antibody watches a running system, diagnoses failures, proposes fixes under human approval, and writes an incident signature to persistent memory — so the next occurrence of the same failure resolves in seconds instead of minutes.

Built for the **All Things Agentic Hackathon** · Track: **Fortified Enterprise Fleet**

---

## The problem

Incident knowledge lives in people's heads and in postmortem docs nobody reads. The same class of failure gets rediagnosed from scratch every time it recurs, by whoever happens to be on call. Meanwhile the tooling that *could* automate diagnosis reads attacker-influenced text — log bodies, alert payloads, ticket descriptions — and most of it does so with no guardrail at all.

Antibody addresses both: durable cross-session incident memory, and a hardened ingest path for untrusted text.

---

## What it does

A monitoring alert fires. Four agents move it down a pipeline:

| Agent | Responsibility | Identity scope |
|---|---|---|
| **Triage** | Classify severity, auto-close noise, decide whether to page a human | none — read alert only |
| **Diagnosis** | Check memory for a matching signature; on a miss, correlate logs, traces, and recent deploys into a structured hypothesis | **read-only** |
| **Response** | Propose a rollback with blast radius, wait for human approval, execute, verify via healthcheck, escalate on failure | **write, gated** |
| **Memory** | Persist the incident signature: symptom fingerprint, root cause, fix applied | write to Memory Bank |

Diagnosis emits a structured hypothesis rather than prose:

```json
{
  "suspect_service": "llm-classifier",
  "suspect_revision": "llm-classifier-00042-xyz",
  "confidence": 0.86,
  "memory_hit": false,
  "evidence": [
    "error rate 0.4% → 31% within 90s of revision rollout",
    "trace spans terminate at classifier→signals publish",
    "no correlated change in upstream scraper"
  ]
}
```

On a memory hit, Diagnosis short-circuits: the hypothesis arrives pre-formed and Response acts immediately. That delta is the point of the system.

---

## What it deliberately does not do

- **It does not act on production unattended.** Response stops at a human approval gate before its write identity unlocks. This is a design commitment, not an unfinished feature.
- **It does not trust what it reads.** Every untrusted-text ingest passes through Model Armor before reaching a model. Log lines are attacker-reachable surface.
- **It does not retry blindly.** A failed post-rollback healthcheck escalates to a human rather than looping.

---

## Architecture

See `docs/architecture.mermaid` for the full diagram.

**Target environment** — a stripped, credential-free copy of a real multi-service trading stack deployed to Cloud Run: `news-scraper → Pub/Sub → llm-classifier → Pub/Sub → execution-layer → Firestore`. The broker is mocked; no live trading credentials exist anywhere in this repo. It serves as a realistic failure surface that can be broken on demand.

**Fleet plane** — four ADK agents on Cloud Run, handing off asynchronously via Pub/Sub, routed and policy-enforced through an Agent Gateway.

**Platform plane**
- **Agent Registry** — versioned catalog, cross-department discovery
- **Memory Bank** — incident signatures and approved-drift decisions, persistent across sessions and weeks
- **Agent Identity** — per-agent service accounts; the read/write split is enforced by IAM, not by prompt
- **Model Armor** — inline guardrail on every untrusted-text ingest
- **Agent Observability** — OpenTelemetry reasoning-chain traces, end to end auditable

---

## Tech stack

- **Model:** Gemini Flash via Vertex AI <!-- TODO: pin the exact model ID; set VERTEX_MODEL_ID in .env -->

- **Agent framework:** Google ADK
- **Compute:** Cloud Run (scale-to-zero throughout; no GKE, no always-on VMs)
- **Messaging:** Pub/Sub
- **State:** Firestore
- **Telemetry:** Cloud Logging, Cloud Trace, Cloud Monitoring
- **Guardrails:** Model Armor

---

## Repository layout

```
agents/
  common/config.py  # shared model ID + GCP coordinates
  triage/           # severity classification, paging decision
  diagnosis/        # memory lookup, log/trace correlation
  response/         # rollback proposal, approval gate, verification
  memory/           # signature extraction and persistence
platform/
  registry/agents.yaml   # agent manifests and versions
  identity/iam.yaml      # service account + IAM definitions
  gateway/               # routing and policy enforcement
target-env/         # purpose-built failure surface (the patient)
  news-scraper/ llm-classifier/ execution-layer/
infra/
  bootstrap.sh          # APIs, topics, Firestore
  deploy-target.sh setup-identity.sh deploy-fleet.sh
  setup-monitoring.sh teardown.sh
demo/
  inject-failure.py     # breaks the classifier on demand
  poisoned-log.py       # emits a prompt-injection log line
  mttr-report.py        # measures run 1 vs run 2
docs/
  architecture.mermaid
```

---

## Spin-up

**Prerequisites:** a GCP project with billing enabled, `gcloud` authenticated, Vertex AI and Model Armor APIs enabled, Python 3.11+.

```bash
# 1. Configure
cp .env.example .env        # set PROJECT_ID, REGION, VERTEX_MODEL_ID
gcloud auth application-default login

# 2. Enable APIs, create topics and the Firestore database
./infra/bootstrap.sh

# 3. Deploy the target environment (the system Antibody watches)
./infra/deploy-target.sh

# 4. Create service accounts and IAM bindings
./infra/setup-identity.sh

# 5. Deploy the agent fleet
./infra/deploy-fleet.sh

# 6. Wire the alert policy into the fleet
./infra/setup-monitoring.sh
```

**Verify it works:**

```bash
python demo/inject-failure.py          # break the classifier
# → watch Triage fire, Diagnosis investigate, Response request approval

python demo/poisoned-log.py            # attempt prompt injection via log body
# → Model Armor blocks; see the block event in Cloud Trace

python demo/inject-failure.py --repeat # same failure class, later
python demo/mttr-report.py             # memory hit; compare run 1 vs run 2
```

**Teardown:** `./infra/teardown.sh` — everything scales to zero, but this removes the deployments entirely.

---

## Registry roadmap

The registry additionally catalogs agents that are **declared but not implemented**, marked `status: registered / not implemented`. They are listed to demonstrate the discovery and versioning surface, and are honestly labeled as unbuilt:

- `config-drift-detector` — scheduled diff against expected revision state
- `cost-optimizer` — idle-resource identification
- `capacity-planner` — pre-emptive scaling recommendations

---

## Findings and learnings

_To fill in before submission: what the memory hit actually saved, what Model Armor caught that naive prompting did not, where the identity split forced better design, and what broke._

---

## License

MIT
