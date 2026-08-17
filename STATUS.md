# Status — Scaffold Complete, Nothing Runs Yet

**As of:** Mon Aug 17 2026, ~18:20 EDT (Phase 0, Day 1)
**Deadline:** Mon Aug 31, 5:00pm PDT

This document records exactly what exists, what has been verified, and what remains.
It is deliberately pessimistic about status: nothing is marked done unless it has
been run. Companion to [build-order.md](build-order.md), which holds the schedule.

---

## Current state in one line

The repository layout, configuration, and infrastructure skeletons exist. **No agent
logic is written, no GCP resource has been created, and no code has been executed
against Vertex AI.**

---

## What was created

### Configuration

| File | State | Notes |
|---|---|---|
| `.gitignore` | done | Ignores `.env`, `.adk/`, `__pycache__`, and `*service-account*.json` |
| `.env.example` | done | Every variable the project needs, with `VERTEX_MODEL_ID` left blank on purpose |
| `requirements.txt` | done | ADK, GCP clients, FastAPI, OTel. Loose lower bounds, unpinned |
| `agents/common/config.py` | functional | Loads `.env`, raises a named error on any missing required var |

`config.py` is the single source for `MODEL_ID`, `PROJECT_ID`, and `REGION`. All
four agents import from it, so the model ID is set in one place.

### Agents — all four are stubs

`agents/{triage,diagnosis,response,memory}/` each contain `__init__.py` and
`agent.py`. Every `agent.py` declares a `root_agent` with a real name, a real
description, `instruction="STUB — not yet implemented."`, and TODO comments naming
the build-order day it is due.

The packages are shaped so `adk web agents/` will list all four side by side —
but only after `.env` is filled in, because `config.py` fails loudly without it.

### Platform

| File | State | Notes |
|---|---|---|
| `platform/registry/agents.yaml` | done, as data | All 7 agents. **Every one reads `status: registered / not implemented`** — accurate today |
| `platform/identity/iam.yaml` | done, as data | Per-agent SAs and role lists. `sa-diagnosis` has no write role, by design |
| `platform/gateway/README.md` | placeholder | Day 8 checklist only |

`iam.yaml` is documentation. `setup-identity.sh` holds the same role lists in bash
arrays and is what actually runs — **the two must be kept in sync by hand.**

### Infrastructure scripts

| Script | State |
|---|---|
| `infra/_common.sh` | functional — sources `.env`, validates `PROJECT_ID`/`REGION`, defines shared arrays |
| `infra/bootstrap.sh` | mostly functional — enables 10 APIs, creates 4 Pub/Sub topics; Firestore DB creation is a TODO |
| `infra/setup-identity.sh` | functional — creates 4 SAs, binds all roles; prints the impersonation command for verifying denial |
| `infra/deploy-target.sh` | functional for deploy — Pub/Sub push subscriptions are a TODO |
| `infra/deploy-fleet.sh` | **`exit 1`** — agents have no container entry point yet |
| `infra/setup-monitoring.sh` | **`exit 1`** — alert policy and notification channel are TODOs |
| `infra/teardown.sh` | functional — requires typing the project ID to confirm; leaves SAs and Firestore data alone |

All are `chmod +x`. Where a script would have required guessing at an undecided
detail, it stops rather than doing something plausible-but-wrong.

### Target environment

`target-env/{news-scraper,llm-classifier,execution-layer}/` each have `main.py`
(a FastAPI app with only `/healthz`), a `Dockerfile`, and a `requirements.txt`.
The Dockerfiles are complete and Cloud Run-ready — they respect `$PORT`.

`target-env/README.md` records the decision to **build a purpose-built fake rather
than port the real trading stack**, and lists the five properties each service must
actually have (structured logs, trace propagation, `/healthz`, an injectable failure
mode, distinct revisions to roll back to).

### Demo scripts

`demo/inject-failure.py`, `poisoned-log.py`, `mttr-report.py` — all three
`raise SystemExit("not implemented")` rather than failing silently. Each carries
TODOs naming the specific trap for that demo, e.g. `--repeat` must reproduce the
*same* symptom fingerprint or the memory lookup cannot match.

### README edits

Four changes, all for internal consistency:

1. `architecture.mermaid` moved to `docs/`; the reference on line 60 updated to match the layout block, which already said `docs/`
2. `bootstrap.sh` added as spin-up step 2; steps 3–6 renumbered
3. Layout block updated to reflect what now exists
4. **"Gemini 3.5 Flash" changed to "Gemini Flash" with a TODO.** That model does not exist; no substitute ID was invented

---

## What was verified

- `bash -n` passes on all 7 shell scripts
- `python -m compileall` passes on `agents/`, `demo/`, `target-env/`
- `git check-ignore` confirms `.env` and `.adk/session.db` are excluded
- 41 files staged

## What was NOT verified

- **The YAML files were never parsed** — `pyyaml` is not installed locally
- No script has been executed. `bash -n` catches syntax, not a wrong gcloud flag
- No `gcloud` command in any script has been run against a real project
- The ADK stubs have never been imported — `google-adk` is not installed

---

## Blockers before anything can run

These are hard prerequisites, all currently unmet:

1. `google-adk` is **not installed** in the active Python (`/home/george/miniconda3/bin/python3`)
2. `gcloud` has **no authenticated account and no configured project**
3. `.env` exists but is **0 bytes**
4. `VERTEX_MODEL_ID` is **unset**, and the correct value is not yet known

---

## Open decisions

**The approval gate mechanism (needed by Day 5, affects Day 10).**
`sa-response` currently holds `roles/run.developer` as a standing grant, which
means it can write to prod at rest — the opposite of the claim in the README.
Three candidates, none chosen: conditional IAM binding; a short-lived token minted
after approval; a separate privileged SA impersonated only post-approval. This is
noted in both `iam.yaml` and `setup-identity.sh`.

**Agent naming is inconsistent across documents.**
README and all code use **Response** and **Memory**. `build-order.md` and
`docs/architecture.mermaid` use **Remediation** and **Postmortem**. The diagram
appears in the demo video — reconcile before Day 10.

**The leftover root agent.**
`agent.py` and `__init__.py` at the repo root are `adk create` output. `agent.py`
still has `model='<FILL_IN_MODEL>'` and `name=''`, and will error if invoked. Now
that `agents/` exists it is redundant. Left in place because whether the root agent
becomes the Gateway entry point is an unmade design decision.

**Memory Bank storage backend.**
The README says "Memory Bank"; `config.py` and `iam.yaml` currently assume a
Firestore collection (`incident-signatures`) with `datastore.*` roles. If Vertex AI
Agent Engine Memory Bank is meant instead, the IAM roles are wrong and must change
before Day 6.

---

## What needs to be finished

Ordered by dependency, not by preference. Days refer to [build-order.md](build-order.md).

### Immediate — unblock everything (Day 1, tonight)

- [ ] `gcloud auth login` and `gcloud auth application-default login`
- [ ] Create/select the GCP project; confirm billing and the $150 credits
- [ ] **Set the $40 billing alert** — the plan calls for this on Day 1
- [ ] `pip install -r requirements.txt`
- [ ] Find the real Flash model ID in the Vertex model garden; set `VERTEX_MODEL_ID`
- [ ] `cp .env.example .env` and fill in every blank
- [ ] Run `./infra/bootstrap.sh` — first real test of the scripts, expect fixes
- [ ] Add the Firestore database creation command to `bootstrap.sh`
- [ ] **Get one agent answering locally via `adk run agents/triage`.** This is the actual Phase 0 risk — auth, not code

### Day 1 (remainder) — target environment

- [ ] Implement all three services, ~50 lines each. Past that, they are doing work the demo does not need
- [ ] Structured JSON logs with a stable `service` field
- [ ] The injectable failure mode in `llm-classifier` — error rate 0% → 30%+ in seconds
- [ ] `./infra/deploy-target.sh`, then add the Pub/Sub push subscriptions
- [ ] Confirm logs land in Cloud Logging

### Day 2 — two-agent handoff

- [ ] Triage instruction and structured verdict output (sev1–sev4, auto-close, page decision)
- [ ] Triage → Diagnosis state handoff
- [ ] Container entry point for ADK agents behind HTTP, then remove the `exit 1` from `deploy-fleet.sh`
- [ ] Run `./infra/setup-identity.sh`
- [ ] **Verify the denial** — impersonate `sa-diagnosis`, attempt a Cloud Run update, confirm `PERMISSION_DENIED`

### Day 3 — the gate

- [ ] Alert policy JSON, kept in `infra/` for reproducibility
- [ ] Pub/Sub notification channel on the incidents topic
- [ ] Triage push-subscribed to incidents; remove the `exit 1` from `setup-monitoring.sh`
- [ ] Break the classifier, watch Triage fire unattended
- [ ] **Decision point.** Full fleet, or drop to the Taskmaster fallback

### Days 4–7 — the spine

- [ ] Diagnosis: Cloud Logging, Cloud Trace, and Cloud Run revision tools; structured hypothesis output
- [ ] Response: rollback proposal with blast radius; approval gate; post-rollback healthcheck that **escalates rather than retries**
- [ ] Memory: signature schema and persistence. **Design the fingerprint key shape before writing the extraction prompt** — Diagnosis has to match on it
- [ ] Diagnosis gains the memory lookup step at the top of its flow (Day 6 — protect this day)
- [ ] Registry: update statuses only as each agent genuinely starts working

### Days 8–10 — the set-pieces

- [ ] Model Armor template; inline on every untrusted-text ingest in the gateway
- [ ] `poisoned-log.py`, plus a without-armor control run for contrast
- [ ] **Record the block on video the day it works** — do not save it for Day 12
- [ ] `inject-failure.py --repeat` and `mttr-report.py`; confirm run 2 is visibly shorter
- [ ] OTel reasoning-chain traces exported to Cloud Trace
- [ ] Identity denial demo; export the architecture diagram to PNG

### Days 11–14 — ship

- [ ] Freeze code Day 11; demo video Day 12; write-up Day 13; **submit Sat Aug 30**
- [ ] Fill in the README's empty "Findings and learnings" section
- [ ] Update every `status:` in `agents.yaml` to the truth as of submission

---

## Standing risk, restated

`build-order.md` names it: the Memory Bank is load-bearing. If Day 6 slips, the
"weeks of async context" claim collapses and the submission is shallow log
summarization in a crowded field. The MTTR delta and the injection block are the
entire differentiation. Everything in the Immediate section above exists to buy
time for Days 6, 8, and 9.
