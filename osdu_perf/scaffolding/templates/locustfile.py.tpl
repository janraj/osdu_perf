"""Locustfile scaffolded by ``osdu_perf init``.

Subclass :class:`PerformanceUser` and register one or more ``BaseService``
implementations. The framework handles authentication, headers, and Kusto
telemetry so your task methods can focus on the actual API calls.
"""

# ----------------------------------------------------------------------------
# Bootstrap: when running on Azure Load Testing or AKS, the osdu_perf wheel is
# uploaded as an additional artifact next to this file. ALT's pip phase runs
# from "/", and the AKS image baking sometimes drops the package install if the
# requirements.txt only listed PyPI deps. So we install the local wheel here on
# import (cheap no-op when osdu_perf is already importable).
# ----------------------------------------------------------------------------
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_WHEELS = sorted(_HERE.glob("osdu_perf-*.whl"))
if _WHEELS:
    try:
        import osdu_perf  # noqa: F401
    except ImportError:
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--force-reinstall",
                str(_WHEELS[-1]),
            ]
        )

from locust import task

from osdu_perf import PerformanceUser, ServiceRegistry


class OsduUser(PerformanceUser):
    """Runs every discovered service in round-robin fashion."""

    def on_start(self) -> None:
        self._registry = ServiceRegistry()
        self._registry.discover(self.client)
        for service in self._registry.services:
            service.test_run_id = self.osdu_context.test_run_id
            service.prehook(
                headers=self.get_headers(),
                partition=self.get_partition(),
                host=self.get_host(),
            )

    @task
    def run_services(self) -> None:
        for service in self._registry.services:
            service.execute(
                headers=self.get_request_headers(),
                partition=self.get_partition(),
                host=self.get_host(),
            )

    def on_stop(self) -> None:
        for service in self._registry.services:
            service.posthook(
                headers=self.get_headers(),
                partition=self.get_partition(),
                host=self.get_host(),
            )
