#!/usr/bin/env bash
# Wires the Cloud Monitoring alert policy into the fleet:
#   error-rate spike -> alert policy -> notification channel -> Pub/Sub -> Triage
#
# This is the Day 3 gate. If this chain runs unattended, commit to the full fleet.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

# TODO(day3): create a Pub/Sub notification channel on $TOPIC_INCIDENTS.
#   gcloud beta monitoring channels create --channel-content-from-file=...
# TODO(day3): create the alert policy — llm-classifier error rate over threshold.
#   gcloud alpha monitoring policies create --policy-from-file=...
#   Keep the policy JSON in this directory so it is reproducible.
# TODO(day3): push-subscribe the Triage agent to $TOPIC_INCIDENTS.

echo "Not implemented — see TODOs in this script."
exit 1
