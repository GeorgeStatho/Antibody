#!/usr/bin/env bash
# Removes all deployments. Everything scales to zero anyway — only run this when
# you are done with the demo video.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

echo "This deletes all Antibody Cloud Run services and Pub/Sub topics in ${PROJECT_ID}."
read -r -p "Type the project ID to confirm: " confirm
[[ "$confirm" == "$PROJECT_ID" ]] || { echo "aborted"; exit 1; }

for svc in "${TARGET_SERVICES[@]}"; do
  step "Deleting service $svc"
  gcloud run services delete "$svc" --region="$REGION" --quiet 2>/dev/null || true
done

for agent in "${FLEET_AGENTS[@]}"; do
  step "Deleting service ${agent}-agent"
  gcloud run services delete "${agent}-agent" --region="$REGION" --quiet 2>/dev/null || true
done

for topic in "$TOPIC_RAW_ARTICLES" "$TOPIC_SIGNALS" "$TOPIC_INCIDENTS" "$TOPIC_APPROVALS"; do
  step "Deleting topic $topic"
  gcloud pubsub topics delete "$topic" --quiet 2>/dev/null || true
done

# Service accounts, IAM bindings, Firestore data, and the alert policy are left
# in place deliberately — deleting them is slow to undo and costs nothing to keep.
echo
echo "Done. Service accounts and Firestore data were NOT deleted."
