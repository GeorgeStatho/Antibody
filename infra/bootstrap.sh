#!/usr/bin/env bash
# One-time project setup. Run this first, before anything else.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

step "Setting active project to $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

step "Enabling APIs (this takes a few minutes on a fresh project)"
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  pubsub.googleapis.com \
  firestore.googleapis.com \
  logging.googleapis.com \
  cloudtrace.googleapis.com \
  monitoring.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  modelarmor.googleapis.com

step "Creating Pub/Sub topics"
for topic in "$TOPIC_RAW_ARTICLES" "$TOPIC_SIGNALS" "$TOPIC_INCIDENTS" \
             "$TOPIC_VERDICTS" "$TOPIC_APPROVALS" "$TOPIC_DEAD_LETTER"; do
  # gcloud reports success on stderr, so without this the loop is silent exactly
  # when it did something and loud only when it did not.
  if gcloud pubsub topics create "$topic" >/dev/null 2>&1; then
    echo "  created $topic"
  else
    echo "  topic $topic already exists"
  fi
done

step "Firestore database"
gcloud firestore databases describe --database="$FIRESTORE_DATABASE" >/dev/null 2>&1 \
  && echo "  database $FIRESTORE_DATABASE already exists" \
  || gcloud firestore databases create \
       --database="$FIRESTORE_DATABASE" \
       --location="$REGION" \
       --edition=standard \
       --type=firestore-native

step "Log-based metric: $METRIC_CLASSIFIER_ERRORS"
# The alert policy fires on this metric, and Triage hashes its name into every
# symptom fingerprint. RENAMING IT ORPHANS EVERY SIGNATURE IN THE MEMORY BANK.
gcloud logging metrics describe "$METRIC_CLASSIFIER_ERRORS" >/dev/null 2>&1 \
  && echo "  metric $METRIC_CLASSIFIER_ERRORS already exists" \
  || gcloud logging metrics create "$METRIC_CLASSIFIER_ERRORS" \
       --description="llm-classifier classification failures" \
       --log-filter="resource.type=\"cloud_run_revision\"
resource.labels.service_name=\"llm-classifier\"
jsonPayload.event=\"classify_failed\""

step "Done"
cat <<'EOF'

Remaining manual steps — do these now, not later:
  1. Set a billing alert at $40 on the billing account.
  2. Confirm the $150 credits are applied.
  3. Run: gcloud auth application-default login
EOF
