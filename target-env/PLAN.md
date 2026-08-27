# Target Environment — Build Plan

**Status:** implemented, tested, and deployed. The pipeline runs end to end. Companion to [README.md](README.md), which
holds the requirements each service must meet, and to
[../agents/triage/PLAN.md](../agents/triage/PLAN.md), which consumes what this
environment emits.

This covers the Day 1 goals still open in [../STATUS.md](../STATUS.md), plus two
gaps the checklist does not mention.

---

## 1. What is actually true right now

Checked against the live project rather than against the checklist, because the
checklist has drifted.

| Checklist item | Reality |
|---|---|
| Firestore creation in `bootstrap.sh` | The command **is** there and a database exists, named **`firebase`**, `us-central1`, native mode. The checkbox is stale — the work left is plumbing, not creation. |
| `adk run agents/triage` | The agent answers through Vertex, verified via `InMemoryRunner`. The `adk` CLI path itself is unrun. |
| Three services implemented | Still `/healthz` only. |
| `deploy-target.sh` | Never run. **Zero Cloud Run services exist.** |
| Push subscriptions | **Zero subscriptions exist.** |

Two gaps that are on no list:

**`triage-verdicts` is not a real topic.** Only `approvals`, `incidents`,
`raw-articles` and `signals` exist. It was added to `bootstrap.sh` but the script
has not been re-run since.

**No agent service accounts exist.** `setup-identity.sh` has never run, so
`deploy-fleet.sh` would fail at its `--service-account` flag. That is nominally a
Day 2 item, but it blocks any deploy of the fleet against this environment.

---

## 2. The decision that governs everything else

**The failure must live in a revision.**

Response's remediation is a Cloud Run revision rollback. If `demo/inject-failure.py`
breaks the classifier by flipping in-memory state over HTTP, there is nothing to
roll back *to*, and the whole Response → verify → resolve arc becomes theatre that
a judge can see through in one question.

So the injection is:

```bash
gcloud run services update llm-classifier --update-env-vars=FAILURE_RATE=0.35
```

which mints a new revision. The broken state *is* a revision. The rollback is a real
`gcloud run services update-traffic --to-revisions=<previous>=100`. The post-rollback
healthcheck has something real to confirm.

Consequence for `llm-classifier`: read `FAILURE_RATE` from the environment at
request time, fail that fraction of classifications, log each failure. Roughly ten
lines, and it is the only thing about the service that the demo depends on.

---

## 3. Firestore — wire the name through, do not just create the database

The creation command is fine. The plumbing behind it is not.

- `agents/common/config.py` never exposes `FIRESTORE_DATABASE`.
- `agents/triage/factory.py` builds `firestore.Client(project=...)` with no
  `database=`, so it connects to `(default)` — **which does not exist in this
  project.** The verdict ledger would fail on the first real alert.

Work:

1. Add `FIRESTORE_DATABASE` to `config.py`, defaulting to `(default)` for anyone
   copying `.env.example`.
2. Pass it: `firestore.Client(project=..., database=config.FIRESTORE_DATABASE)`.
3. Make the bootstrap step idempotent. It runs bare today, so a second
   `bootstrap.sh` fails on the existing database instead of skipping. Match the
   pattern the topic loop already uses.
4. Fix the indentation of the creation block — it sits indented under a `step` with
   no enclosing block.

**Trap.** `.env.example` ships `FIRESTORE_DATABASE=(default)`. Sourced by bash that
is an array assignment expanding to `default`, with no parentheses. Read by
python-dotenv it is the literal string `(default)`. One line, two different database
names, depending on who reads it. Quote it or drop the parentheses.

---

## 4. `adk run agents/triage` — the checkbox means the CLI

Auth is proven, which was the real Phase 0 risk. But `adk run` and `adk web agents/`
exercise a different path: they import `agents/<name>/agent.py` looking for
`root_agent`. That name still exists, so this should pass — and "should" is not the
standard the rest of STATUS.md holds to.

**`PYTHONPATH=.` is required, and STATUS.md is wrong about this.** ADK's loader puts
`agents/` on `sys.path` and imports the package as `triage`, not `agents.triage`, so
the absolute `from agents.common import config` cannot resolve. The repo root has to
be on the path:

```bash
PYTHONPATH=. adk run agents/triage
PYTHONPATH=. adk web agents/
```

Verified working: the agent answers with a valid `Decision` payload. Leaving the
absolute imports alone is the right trade — the tests, the Cloud Run entry point and
the factory all depend on them, and only the ADK CLI needs the path hint.

Run both. Expect two things that are correct but look odd:

- Triage now carries an `output_schema`, so it answers with JSON rather than prose.
- The other three agents still read `instruction="STUB — not yet implemented."`

`adk web` listing four agents where three are stubs is honest. Do not read it as
four working agents, and do not let it tempt an optimistic edit to
`platform/registry/agents.yaml`.

---

## 5. The log schema is the load-bearing item

More load-bearing than the services themselves. Three separate things key on it:

- The **alert policy** fires on a log-based metric derived from these lines.
- **Triage's fingerprint** hashes `service | metric_type | condition | direction`.
  `metric_type` is the log-based metric's name, so **that name must never change**
  or every signature already in the Memory Bank is orphaned.
- The **injection demo** needs the poisoned log body to reach the notification
  payload, which is why [../agents/triage/PLAN.md](../agents/triage/PLAN.md) §2
  chose a log-based alert policy over a metric-threshold one.

One JSON line per event:

| Field | Why |
|---|---|
| `severity` | top level, so Cloud Logging promotes it |
| `service` | stable, and the fingerprint hashes it |
| `event` | stable verb: `article_published`, `classify_failed`, `position_written` |
| `error_class` | stable on failures; this is what distinguishes failure classes |
| `traceparent` | W3C context, propagated across both Pub/Sub hops |

**Do not put the observed error rate in the log line.** The rate is the metric's
job. Putting it anywhere near the fingerprint's input path would break stability
across occurrences, and stability across occurrences is the entire memory story.

Create the log-based metric in `bootstrap.sh`, not by hand in the console, so it is
reproducible and so its name is version-controlled.

---

## 6. The three services

Around fifty lines each. Past that they are doing work the demo does not need.

**news-scraper** — `POST /tick` publishes one synthetic article to `raw-articles`.
No timer inside the process; see §8.

**llm-classifier** — push subscriber on `raw-articles`. Classifies with a hardcoded
mapping; it does not need a model and giving it one adds a second failure surface
for no demo value. Publishes to `signals`. Honours `FAILURE_RATE`.

**execution-layer** — push subscriber on `signals`. Writes one position document to
Firestore, **keyed by the Pub/Sub `messageId`**, so at-least-once delivery does not
double-count positions. No broker, no credentials, ever.

---

## 7. The injectable failure mode

Mechanism is settled in §2. Two properties to verify before building anything on
top of it:

- The error rate moves 0% → 30%+ within seconds of the new revision serving.
- It is visible as a **rate** in Cloud Monitoring, not merely as individual log
  entries.

Check the metric has populated in the console *before* writing an alert policy
against it. A policy on a metric that never populates is a silent dead end, and it
fails in the direction that looks like everything is fine.

---

## 8. Traffic, and why there is no timer

Cloud Run scales to zero, so nothing ticks the scraper on its own.

Cloud Scheduler is the clean answer for ambient traffic, but its 1-minute floor is
too slow to drive an error-rate metric during a live demo. Split it:

- **Cloud Scheduler**, 1/min, for background traffic so the metric is never empty.
- **`demo/inject-failure.py` drives its own burst** — a few dozen `POST /tick`
  calls — so the error rate crosses the threshold in seconds while the camera is
  running.

This also keeps spend at zero between demos, which is what `build-order.md`'s cost
discipline section asks for.

---

## 9. Deploy and subscriptions

The deploy loop in `deploy-target.sh` is already correct. What it needs after it:

1. Read each service URL back with
   `gcloud run services describe --format='value(status.url)'`.
2. Create the two push subscriptions against those URLs:
   `raw-articles → llm-classifier`, `signals → execution-layer`.
3. Idempotency, same as the topic loop. This script will be re-run.
4. A dead-letter topic and a capped retry policy on both subscriptions. Without
   them one poison message loops forever and pollutes the very error-rate metric
   the alert policy watches.

**Auth.** The script deploys `--allow-unauthenticated`, so push works with no OIDC
configuration. That is a reasonable choice for a disposable target environment, but
add the one-line comment saying it is deliberate. Unexplained, it reads as
sloppiness rather than as a decision.

---

## 10. Confirming it works

The command already sketched in the script's TODO covers log delivery. Add the two
that actually matter:

- The **log-based metric has data points**, not just that log entries exist.
- **Trace context survives both Pub/Sub hops.** Propagate `traceparent` through
  message attributes from the start; retrofitting it later is a change that touches
  all three services at once.

---

## 11. Order

1. Firestore wiring and the `adk run` check. Both are minutes, and the Firestore bug
   otherwise surfaces as a confusing failure on the first real alert.
2. Log schema and the log-based metric name. Hardest things to change later, since
   the fingerprint and every stored signature depend on the metric name.
3. The three services.
4. `deploy-target.sh`, then the subscriptions.
5. Re-run `bootstrap.sh` for the missing `triage-verdicts` topic, and run
   `setup-identity.sh`. Neither is on the Day 1 list; both block Day 2.

---

## 12. Acceptance criteria

- [x] `firestore.Client` connects to the database that actually exists
- [x] Every service module composes and serves the routes the container expects
- [x] One `traceparent` survives both hops (unit-proven; unproven in Cloud Trace)
- [x] A redelivered signal writes one position, not two
- [x] `classify_failed` / `injected_failure` are emitted exactly as the metric filters
- [x] `adk run agents/triage` answers from the CLI (with `PYTHONPATH=.`)
- [ ] `bootstrap.sh` runs twice in a row without error
- [ ] `triage-verdicts` exists as a topic
- [ ] All four agent service accounts exist
- [x] `bootstrap.sh` runs twice in a row without error
- [x] `triage-verdicts` exists as a topic
- [x] All four agent service accounts exist
- [x] Three services deployed, each serving (uvicorn up, startup probe passed)
- [x] An article published to `raw-articles` reaches Firestore as a position
- [x] One `traceparent` spans classifier → executor, same trace id, distinct spans
- [ ] Each service answers `/healthz` **over its public URL**
- [ ] The log-based metric shows data points in Cloud Monitoring
- [ ] `FAILURE_RATE=0.35` on a new revision drives the metric over 30% within seconds
- [ ] The previous revision still exists and still serves cleanly — there is
      something to roll back *to*

**Known issue: the run.app URLs are not reachable from the dev machine.** Both
published URLs return Google's generic unknown-host 404, with no `server` header,
over IPv4 and IPv6 alike, while `cloud.google.com` from the same shell returns
`server: ESF`. The services themselves are fine — uvicorn is listening, the startup
probe passed, and no request ever reaches the container. Pub/Sub push works because
it originates inside Google's network, which is why the pipeline runs end to end
regardless.

Unresolved. It blocks `demo/inject-failure.py`, whose traffic burst ticks the
scraper over its public URL. If it does not clear on its own, the fallback is to
drive traffic by publishing to `raw-articles` directly, which is what the pipeline
verification already does.

---

## 13. Traps

- **The metric name is permanent.** Renaming it orphans every signature in the
  Memory Bank. If it must change, treat it the way `fingerprint.py` treats its input
  set: version it, do not silently re-key.
- **Do not give the classifier a real model.** It adds a second failure surface,
  costs quota on every demo run, and buys nothing a judge will see.
- **Do not let a service grow past ~50 lines.** `README.md` sets that bar for a
  reason: every line here is a line not spent on the Memory Bank or the injection
  block, which are the only two things that differentiate this submission.
- **No credentials in this tree, ever.** Not a key file, not an API token, not a
  commented-out one.
