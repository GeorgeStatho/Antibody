#!/usr/bin/env python3
"""Breaks the classifier on demand, and drives the traffic that makes it visible.

The failure is injected as an environment variable change, which mints a NEW Cloud
Run REVISION. That is the whole point: the Response agent's remediation is a
revision rollback, so the broken state has to be a revision or there is nothing to
roll back to and the remediation is a gesture rather than an operation.

    python demo/inject-failure.py            # break it, then drive traffic
    python demo/inject-failure.py --repeat   # heal, then break the same way again
    python demo/inject-failure.py --heal     # restore the healthy rate

`--repeat` reproduces the SAME failure class deliberately: the same service, the
same error_class, the same log event, so the symptom fingerprint is identical and
the Memory Bank lookup can match. Change any of those and the second run reads as a
first occurrence, which is the whole MTTR story lost to a detail.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass

CLASSIFIER_SERVICE = "llm-classifier"
SCRAPER_SERVICE = "news-scraper"

BROKEN_RATE = "0.35"
HEALTHY_RATE = "0"

DEFAULT_TICKS = 40
REQUEST_TIMEOUT_SECONDS = 30
RECOVERY_PAUSE_SECONDS = 20


class CommandFailed(RuntimeError):
    """A gcloud invocation failed. Reported plainly rather than swallowed."""


@dataclass(frozen=True)
class Project:
    """The coordinates every gcloud call needs. Read once, passed down."""

    project_id: str
    region: str

    @classmethod
    def from_environment(cls) -> "Project":
        project_id = os.environ.get("PROJECT_ID")
        if not project_id:
            raise SystemExit("PROJECT_ID is not set — source .env first")
        return cls(project_id=project_id, region=os.environ.get("REGION", "us-central1"))


class CloudRun:
    """The Cloud Run operations this demo needs, and nothing else."""

    def __init__(self, project: Project) -> None:
        self._project = project

    def set_failure_rate(self, service: str, rate: str) -> None:
        self._run("run", "services", "update", service,
                  f"--update-env-vars=FAILURE_RATE={rate}", "--quiet")

    def service_url(self, service: str) -> str:
        return self._run("run", "services", "describe", service,
                         "--format=value(status.url)").strip()

    def _run(self, *arguments: str) -> str:
        command = ["gcloud", *arguments,
                   f"--project={self._project.project_id}",
                   f"--region={self._project.region}"]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise CommandFailed(result.stderr.strip() or " ".join(command))
        return result.stdout


class TrafficBurst:
    """Ticks the scraper directly.

    Cloud Scheduler's one-minute floor is too slow to move an error-rate metric
    while a camera is running, so the demo drives its own traffic.
    """

    def __init__(self, scraper_url: str, ticks: int = DEFAULT_TICKS) -> None:
        self._scraper_url = scraper_url
        self._ticks = ticks

    def send(self) -> int:
        return sum(1 for _ in range(self._ticks) if self._tick())

    def _tick(self) -> bool:
        request = urllib.request.Request(f"{self._scraper_url}/tick", method="POST")
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS):
                return True
        except OSError as error:
            print(f"  tick failed: {error}", file=sys.stderr)
            return False


class Demo:
    """Each method is one complete demo action. No shared mutable state between them."""

    def __init__(self, cloud_run: CloudRun, ticks: int) -> None:
        self._cloud_run = cloud_run
        self._ticks = ticks

    def inject(self) -> None:
        print(f"Injecting FAILURE_RATE={BROKEN_RATE} into {CLASSIFIER_SERVICE} (new revision)")
        self._cloud_run.set_failure_rate(CLASSIFIER_SERVICE, BROKEN_RATE)
        self._drive_traffic()
        print("\nWatch Triage fire. The previous revision is intact, so there is something")
        print("to roll back to — which is what makes the Response remediation an operation.")

    def heal(self) -> None:
        print(f"Restoring FAILURE_RATE={HEALTHY_RATE} on {CLASSIFIER_SERVICE}")
        self._cloud_run.set_failure_rate(CLASSIFIER_SERVICE, HEALTHY_RATE)
        self._drive_traffic()

    def repeat(self) -> None:
        """The same failure class again, so the fingerprint matches the first run."""
        self.heal()
        print(f"\nLetting the metric settle for {RECOVERY_PAUSE_SECONDS}s")
        time.sleep(RECOVERY_PAUSE_SECONDS)
        self.inject()

    def _drive_traffic(self) -> None:
        url = self._cloud_run.service_url(SCRAPER_SERVICE)
        print(f"Driving {self._ticks} ticks at {url}")
        print(f"  {TrafficBurst(url, self._ticks).send()} delivered")


def select_action(arguments: argparse.Namespace):
    """One flag, one method. No branching inside the demo itself."""
    if arguments.heal:
        return Demo.heal
    if arguments.repeat:
        return Demo.repeat
    return Demo.inject


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Break the classifier on demand.")
    parser.add_argument("--repeat", action="store_true",
                        help="heal, settle, then break the same way — identical fingerprint")
    parser.add_argument("--heal", action="store_true", help="restore the healthy rate")
    parser.add_argument("--ticks", type=int, default=DEFAULT_TICKS,
                        help=f"ticks in the traffic burst (default {DEFAULT_TICKS})")
    return parser.parse_args(argv)


def main() -> int:
    arguments = parse_arguments()
    demo = Demo(CloudRun(Project.from_environment()), arguments.ticks)
    try:
        select_action(arguments)(demo)
    except CommandFailed as error:
        print(f"gcloud failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
