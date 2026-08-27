#!/usr/bin/env bash
# Creates one service account per agent and binds its roles.
# Keep the arrays below in sync with platform/identity/iam.yaml (the doc source).
#
# The read/write split lives here. Do not grant Diagnosis a write role to unblock
# local dev — the Day 10 denial demo depends on that denial being real.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

declare -A AGENT_ROLES=(
  # datastore.user is for Triage's OWN verdict ledger (idempotency + MTTR t0),
  # not for any write to the target environment. The read/write split is about prod.
  [triage]="roles/pubsub.subscriber roles/pubsub.publisher roles/datastore.user"
  [diagnosis]="roles/logging.viewer roles/cloudtrace.user roles/run.viewer roles/datastore.viewer roles/pubsub.publisher"
  [response]="roles/run.developer roles/pubsub.publisher roles/pubsub.subscriber"
  [memory]="roles/datastore.user roles/pubsub.subscriber"
)

for agent in "${FLEET_AGENTS[@]}"; do
  sa="sa-${agent}"
  email="${sa}@${PROJECT_ID}.iam.gserviceaccount.com"

  step "Service account: $sa"
  gcloud iam service-accounts create "$sa" \
    --display-name="Antibody ${agent} agent" 2>/dev/null || echo "  already exists"

  for role in ${AGENT_ROLES[$agent]}; do
    echo "  binding $role"
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="serviceAccount:${email}" \
      --role="$role" \
      --condition=None \
      --quiet >/dev/null
  done
done

step "Verify the denial (do this before trusting the identity story)"
cat <<'EOF'
  Impersonate sa-diagnosis and attempt a Cloud Run revision update.
  It MUST fail with PERMISSION_DENIED. If it succeeds, the demo is dead:
    gcloud run services update <svc> --region=$REGION \
      --impersonate-service-account=sa-diagnosis@$PROJECT_ID.iam.gserviceaccount.com
EOF

# TODO(day5): the approval gate. Decide the mechanism before building Response —
# conditional binding, post-approval short-lived token, or impersonation of a
# separate privileged SA. Whichever, sa-response must not hold standing write
# authority at rest.
