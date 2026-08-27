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
for topic in "$TOPIC_RAW_ARTICLES" "$TOPIC_SIGNALS" "$TOPIC_INCIDENTS" "$TOPIC_VERDICTS" "$TOPIC_APPROVALS"; do
  gcloud pubsub topics create "$topic" 2>/dev/null || echo "  topic $topic already exists"
done

step "Firestore database"

  gcloud firestore databases create \
      --database=$FIRESTORE_DATABASE \
      --location=$REGION \
      --edition=standard \
      --type=firestore-native

step "Done"
cat <<'EOF'

Remaining manual steps — do these now, not later:
  1. Set a billing alert at $40 on the billing account.
  2. Confirm the $150 credits are applied.
  3. Run: gcloud auth application-default login
EOF
