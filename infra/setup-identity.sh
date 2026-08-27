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

# A freshly created service account is not immediately bindable: IAM returns
# "does not exist" for a few seconds after create() succeeds. Wait for it rather
# than retrying blindly, so a genuine failure still surfaces as a failure.
SA_WAIT_ATTEMPTS=12
SA_WAIT_SECONDS=5

wait_for_service_account() {
  local email="$1" attempt
  for ((attempt = 1; attempt <= SA_WAIT_ATTEMPTS; attempt++)); do
    if gcloud iam service-accounts describe "$email" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$SA_WAIT_SECONDS"
  done
  echo "error: $email never became visible to IAM" >&2
  return 1
}

# The binding itself can also lose the race even once the account is describable.
BIND_ATTEMPTS=5

bind_role() {
  local email="$1" role="$2" attempt
  for ((attempt = 1; attempt <= BIND_ATTEMPTS; attempt++)); do
    if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
         --member="serviceAccount:${email}" \
         --role="$role" \
         --condition=None \
         --quiet >/dev/null 2>&1; then
      return 0
    fi
    sleep "$SA_WAIT_SECONDS"
  done
  echo "error: could not bind $role to $email" >&2
  return 1
}

for agent in "${FLEET_AGENTS[@]}"; do
  sa="sa-${agent}"
  email="${sa}@${PROJECT_ID}.iam.gserviceaccount.com"

  step "Service account: $sa"
  if gcloud iam service-accounts create "$sa" \
       --display-name="Antibody ${agent} agent" >/dev/null 2>&1; then
    echo "  created $sa"
  else
    echo "  $sa already exists"
  fi
  wait_for_service_account "$email"

  for role in ${AGENT_ROLES[$agent]}; do
    echo "  binding $role"
    bind_role "$email" "$role"
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
