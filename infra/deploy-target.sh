#!/usr/bin/env bash
# Deploys the target environment — the stack Antibody watches and breaks.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

for svc in "${TARGET_SERVICES[@]}"; do
  step "Deploying $svc"
  gcloud run deploy "$svc" \
    --source="$REPO_ROOT/target-env/$svc" \
    --region="$REGION" \
    --min-instances=0 \
    --allow-unauthenticated \
    --set-env-vars="PROJECT_ID=${PROJECT_ID},TOPIC_RAW_ARTICLES=${TOPIC_RAW_ARTICLES},TOPIC_SIGNALS=${TOPIC_SIGNALS}" \
    --quiet
done

# TODO(day1): wire the Pub/Sub push subscriptions once the service URLs exist:
#   raw-articles -> llm-classifier
#   signals      -> execution-layer
# TODO(day1): confirm structured logs are landing —
#   gcloud logging read 'resource.labels.service_name="llm-classifier"' --limit=5
