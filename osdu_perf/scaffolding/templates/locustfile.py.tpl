"""Locustfile scaffolded by ``osdu_perf init``.

Subclass :class:`PerformanceUser` and register one or more ``BaseService``
implementations. The framework handles authentication, headers, and Kusto
telemetry so your task methods can focus on the actual API calls.
"""

from locust import task

from osdu_perf import PerformanceUser, ServiceRegistry


class OsduUser(PerformanceUser):
    """Runs every discovered service in round-robin fashion."""

    def on_start(self) -> None:
        self._registry = ServiceRegistry()
        self._registry.discover(self.client)
        for service in self._registry.services:
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
