#!/usr/bin/env bash
# Deploys the four agents to Cloud Run, each under its own service account.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

# TODO(day2): agents are not yet packaged as deployable services. Each needs a
# container entry point wrapping the ADK agent behind HTTP. Decide the shape once
# and reuse it for all four.
echo "Fleet agents are not deployable yet — see TODO in this script."
exit 1

for agent in "${FLEET_AGENTS[@]}"; do
  step "Deploying ${agent}-agent"
  gcloud run deploy "${agent}-agent" \
    --source="$REPO_ROOT" \
    --region="$REGION" \
    --min-instances=0 \
    --no-allow-unauthenticated \
    --service-account="sa-${agent}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --set-env-vars="PROJECT_ID=${PROJECT_ID},REGION=${REGION},VERTEX_MODEL_ID=${VERTEX_MODEL_ID},GOOGLE_GENAI_USE_VERTEXAI=TRUE" \
    --quiet
done
