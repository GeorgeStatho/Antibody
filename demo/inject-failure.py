"""Break the llm-classifier on demand.

Run 1 (`--repeat` absent): the fleet diagnoses from scratch.
Run 2 (`--repeat`): same failure class, days later. Diagnosis should hit memory
and short-circuit. If run 2 isn't visibly shorter, that's the bug to fix first.

STUB — Phase 2, Day 9.
"""

# TODO(day9): flip the classifier into its failure mode (env var or bad revision).
# TODO(day9): stamp a run marker so mttr-report.py can pair run 1 with run 2.
# TODO(day9): --repeat should produce the SAME symptom fingerprint, otherwise the
# memory lookup can't match and the whole payoff evaporates.

raise SystemExit("not implemented")
