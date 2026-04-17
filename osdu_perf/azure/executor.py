"""Start and monitor Azure Load Test runs."""

from __future__ import annotations

import time
from typing import Any

from azure.developer.loadtesting import LoadTestRunClient

from ..errors import AzureResourceError
from ..telemetry import get_logger

_LOGGER = get_logger("azure.executor")

_RUNNING_STATES = {"EXECUTING", "PROVISIONING", "PROVISIONED", "CONFIGURING"}
_FAILED_STATES = {"FAILED", "CANCELLED"}


class TestExecutor:
    """Invoke an existing Azure Load Test and poll until it finishes."""

    def __init__(self, run_client: LoadTestRunClient) -> None:
        self._client = run_client

    def start(self, test_name: str, display_name: str | None = None) -> dict[str, Any]:
        display = _display_name(display_name or f"{test_name}-{int(time.time())}")
        _LOGGER.info("Starting test run '%s' (display='%s')", test_name, display)
        poller = self._client.begin_test_run(
            test_run_id=display,
            body={
                "testId": test_name,
                "displayName": display,
                "description": "Run created by osdu_perf",
                "autoStop": {"errorPercentage": 100, "timeWindow": 60},
            },
        )
        return {
            "testRunId": display,
            "displayName": display,
            "operationStatus": "completed" if poller.done() else "running",
        }

    def status(self, run_id: str) -> dict[str, Any]:
        raw = self._client.get_test_run(test_run_id=run_id)
        return _as_dict(raw)

    def wait(self, run_id: str, *, timeout_s: int = 3600, interval_s: int = 30) -> bool:
        _LOGGER.info("Waiting for run '%s' to finish", run_id)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            info = self.status(run_id)
            state = info.get("status", "UNKNOWN")
            if state == "DONE":
                _LOGGER.info("Run '%s' completed", run_id)
                return True
            if state in _FAILED_STATES:
                _LOGGER.error("Run '%s' ended in state '%s'", run_id, state)
                return False
            if state in _RUNNING_STATES:
                _LOGGER.info("Run '%s' state=%s", run_id, state)
            else:
                _LOGGER.warning("Run '%s' reported unknown state '%s'", run_id, state)
            time.sleep(interval_s)
        _LOGGER.warning("Run '%s' timed out after %ss", run_id, timeout_s)
        return False

    def stop(self, run_id: str) -> None:
        _LOGGER.info("Stopping run '%s'", run_id)
        try:
            self._client.begin_stop_test_run(test_run_id=run_id)
        except Exception as exc:
            raise AzureResourceError(f"Failed to stop test run '{run_id}': {exc}") from exc


def _display_name(name: str) -> str:
    name = name.strip()
    if len(name) < 2:
        name = f"{name}-run"
    if len(name) > 50:
        name = name[:50]
    return name


def _as_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    for attr in ("as_dict", "to_dict"):
        method = getattr(obj, attr, None)
        if callable(method):
            try:
                value = method()
                if isinstance(value, dict):
                    return value
            except Exception:
                pass
    try:
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    except Exception:
        return {}


__all__ = ["TestExecutor"]
