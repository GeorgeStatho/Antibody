#!/usr/bin/env bash
# Deploys the target environment — the stack Antibody watches and breaks.
#
# One image, three services. TARGET_MODULE selects which module each service runs,
# so the shared log schema and trace propagation cannot drift between them.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

module_for() { echo "${1//-/_}"; }

for svc in "${TARGET_SERVICES[@]}"; do
  step "Deploying $svc"
  gcloud run deploy "$svc" \
    --source="$REPO_ROOT/target-env" \
    --region="$REGION" \
    --min-instances=0 \
    --allow-unauthenticated \
    --set-env-vars="TARGET_MODULE=$(module_for "$svc"),PROJECT_ID=${PROJECT_ID},TOPIC_RAW_ARTICLES=${TOPIC_RAW_ARTICLES},TOPIC_SIGNALS=${TOPIC_SIGNALS},FIRESTORE_DATABASE=${FIRESTORE_DATABASE},FIRESTORE_COLLECTION_POSITIONS=${FIRESTORE_COLLECTION_POSITIONS}" \
    --quiet
done

# --allow-unauthenticated is deliberate. This is a disposable target environment
# and the push subscriptions below carry no OIDC token; the AGENT fleet is deployed
# --no-allow-unauthenticated, which is where it matters.

service_url() {
  gcloud run services describe "$1" --region="$REGION" --format='value(status.url)'
}

subscribe() {
  local name="$1" topic="$2" endpoint="$3"
  gcloud pubsub subscriptions describe "$name" >/dev/null 2>&1 \
    && { echo "  subscription $name already exists"; return 0; }
  gcloud pubsub subscriptions create "$name" \
    --topic="$topic" \
    --push-endpoint="$endpoint" \
    --ack-deadline=60 \
    --dead-letter-topic="$TOPIC_DEAD_LETTER" \
    --max-delivery-attempts=5 \
    --quiet
}

step "Wiring push subscriptions"
# Capped retries with a dead-letter topic: without them one poison message loops
# forever and pollutes the error-rate metric the alert policy watches.
subscribe "raw-articles-to-classifier" "$TOPIC_RAW_ARTICLES" "$(service_url llm-classifier)"
subscribe "signals-to-executor" "$TOPIC_SIGNALS" "$(service_url execution-layer)"

step "Deployed"
cat <<EOF

Verify, in this order:

  1. Health:
       curl -s "\$(gcloud run services describe llm-classifier --region=$REGION \\
         --format='value(status.url)')/healthz"

  2. A signal reaches Firestore. Publishing straight to the topic exercises the
     whole pipeline inside Google's network, which also works from a machine that
     cannot reach the run.app URLs:
       gcloud pubsub topics publish $TOPIC_RAW_ARTICLES \\
         --message='{"article_id":"probe","headline":"ACME beats earnings","ticker":"ACME"}' \\
         --attribute="traceparent=00-\$(openssl rand -hex 16)-\$(openssl rand -hex 8)-01"

     There is no \`gcloud firestore documents list\`. Read the collection instead:
       python -c "from google.cloud import firestore; \\
         print([d.to_dict() for d in firestore.Client(project='$PROJECT_ID', \\
         database='$FIRESTORE_DATABASE').collection('$FIRESTORE_COLLECTION_POSITIONS') \\
         .limit(5).stream()])"

  3. Structured logs are landing, and one traceparent spans all three services:
       gcloud logging read 'resource.type="cloud_run_revision" AND jsonPayload.event!=""' \\
         --limit=10 --freshness=10m \\
         --format='value(jsonPayload.service,jsonPayload.event,jsonPayload.traceparent)'

  4. The log-based metric has DATA POINTS, not just matching log entries. A policy
     written against a metric that never populates fails silently, in the direction
     that looks like everything is fine:
       https://console.cloud.google.com/logs/metrics?project=$PROJECT_ID

Note: the run.app URLs may not be reachable from every network. Step 2 exercises the
pipeline from inside Google's network and is the more reliable check.
EOF
