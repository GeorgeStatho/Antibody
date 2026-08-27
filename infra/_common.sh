#!/usr/bin/env bash
# Sourced by every infra script. Not meant to be run directly.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$REPO_ROOT/.env" ]]; then
  echo "error: .env not found. Copy .env.example to .env and fill it in." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$REPO_ROOT/.env"
set +a

: "${PROJECT_ID:?PROJECT_ID is not set in .env}"
: "${REGION:?REGION is not set in .env}"

TARGET_SERVICES=(news-scraper llm-classifier execution-layer)
FLEET_AGENTS=(triage diagnosis response memory)

# The alert policy fires on this metric and Triage hashes its name into every
# symptom fingerprint. Treat the name as permanent: renaming it orphans every
# signature already stored in the Memory Bank.
METRIC_CLASSIFIER_ERRORS="classifier_errors"

# Poison messages land here rather than looping forever and polluting the very
# error-rate metric the alert policy watches.
TOPIC_DEAD_LETTER="dead-letter"

step() { echo; echo "==> $*"; }
