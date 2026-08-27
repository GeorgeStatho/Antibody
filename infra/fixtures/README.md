# Alert fixtures

**These are SYNTHETIC.** They were hand-built against the *documented* Cloud
Monitoring notification shape, because no real alert has fired yet — the alert
policy in `infra/setup-monitoring.sh` does not exist.

They are good enough to develop and test the parser against. They are **not**
evidence that the parser works.

## Replace them with the real thing at the first opportunity

```bash
# with the policy wired and a push subscription pointed at a request bin / local tunnel
python demo/inject-failure.py
# capture the raw POST body, verbatim, to:
#   infra/fixtures/alert-open.captured.json
```

Then diff `alert-open.captured.json` against `alert-open.json`. **Where they
disagree, the captured payload wins** — update `agents/common/alert.py` and
regenerate these files. Field names below that turn out to be wrong are the most
likely first bug in the whole fleet.

## The corpus

| File | Exercises |
|---|---|
| `alert-open.json` | the ordinary sev2 case — classifier error-rate spike |
| `alert-closed.json` | `state: closed` — must auto-close with zero Vertex calls |
| `alert-flap.json` | open <60s, barely over threshold — noise suppression |
| `alert-sev1-executor.json` | execution-layer erroring — the write path, always sev1 |
| `alert-poisoned.json` | prompt injection in the log body reaching `summary` |
| `alert-storm-*.json` | three alerts, one root cause — must group into one verdict |
| `malformed-*.json` | permanently unparseable — must ACK, never retry |

`alert-poisoned.json` carries the injection string from `demo/poisoned-log.py`.
It exists so the Model Armor path can be tested without live Model Armor, and so
there is a regression test that no injected instruction ever reaches `rationale`.
