#!/usr/bin/env bash
# Deploys the implemented agents to Cloud Run, each under its own service account.
#
# HONESTY RULE, same as platform/registry/agents.yaml: only agents that actually
# run are deployed. A stub answering /healthz on Cloud Run looks exactly like a
# working agent from the console, which is the one impression this project must
# never give. Add an agent to IMPLEMENTED_AGENTS when it genuinely serves traffic.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

IMPLEMENTED_AGENTS=(triage)

is_implemented() {
  local candidate="$1"
  for agent in "${IMPLEMENTED_AGENTS[@]}"; do
    [[ "$agent" == "$candidate" ]] && return 0
  done
  return 1
}

for agent in "${FLEET_AGENTS[@]}"; do
  if ! is_implemented "$agent"; then
    echo "  skipping ${agent}-agent — still a stub, see agents/${agent}/agent.py"
    continue
  fi

  step "Deploying ${agent}-agent"
  gcloud run deploy "${agent}-agent" \
    --source="$REPO_ROOT" \
    --region="$REGION" \
    --min-instances=0 \
    --no-allow-unauthenticated \
    --service-account="sa-${agent}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --set-env-vars="FLEET_AGENT=${agent},PROJECT_ID=${PROJECT_ID},REGION=${REGION},VERTEX_MODEL_ID=${VERTEX_MODEL_ID},GOOGLE_GENAI_USE_VERTEXAI=TRUE,TOPIC_VERDICTS=${TOPIC_VERDICTS},TOPIC_INCIDENTS=${TOPIC_INCIDENTS},FIRESTORE_COLLECTION_VERDICTS=${FIRESTORE_COLLECTION_VERDICTS},MODEL_ARMOR_TEMPLATE_ID=${MODEL_ARMOR_TEMPLATE_ID}" \
    --quiet
done

step "Deployed"
cat <<'EOF'

ALLOW_UNSCANNED_PROMPT is deliberately not passed through. It is a development
switch, and a deployed agent must never prompt on text Model Armor did not clear.

Next: ./infra/setup-monitoring.sh to point the alert policy at triage-agent.
EOF
