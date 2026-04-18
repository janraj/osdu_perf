""":class:`PerformanceUser` — the Locust user subclass exposed to test authors."""

from __future__ import annotations

import os
from typing import Any

from locust import HttpUser, between, events

from ..config import load_config
from ..errors import ConfigError
from ..kusto import KustoIngestor
from ..telemetry import get_logger
from . import _events
from ._collector import collect_payload
from .context import RequestContext

_LOGGER = get_logger("testing.user")
_events._register()


class PerformanceUser(HttpUser):
    """Base class for performance tests.

    Subclass in your ``locustfile.py`` and add ``@task`` methods. The class
    wires up OSDU authentication, a per-request correlation-id, and Kusto
    telemetry at test-stop.
    """

    abstract = True
    wait_time = between(1, 3)
    host = "https://localhost"

    # Shared across user instances within this worker.
    _context: RequestContext | None = None
    _banner_printed: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def __init__(self, environment: Any) -> None:
        super().__init__(environment)
        self.logger = _LOGGER
        if PerformanceUser._context is None:
            PerformanceUser._context = self._build_context(environment)
        self.osdu_context = PerformanceUser._context

        if not PerformanceUser._banner_printed:
            self._print_banner(environment)
            PerformanceUser._banner_printed = True

    # ------------------------------------------------------------------
    # Accessors (kept for test authors)
    # ------------------------------------------------------------------
    def get_host(self) -> str:
        return self.osdu_context.host

    def get_partition(self) -> str:
        return self.osdu_context.partition

    def get_appid(self) -> str:
        return self.osdu_context.app_id

    def get_token(self) -> str:
        return self.osdu_context.bearer_token

    def get_headers(self) -> dict[str, str]:
        return self.osdu_context.default_headers

    def get_request_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        return self.osdu_context.request_headers(extra)

    def new_correlation_id(self) -> str:
        return self.osdu_context.new_correlation_id()

    # ------------------------------------------------------------------
    # HTTP convenience wrappers
    # ------------------------------------------------------------------
    def get(self, endpoint: str, name: str | None = None, headers=None, **kwargs):
        return self._request("GET", endpoint, name, headers, **kwargs)

    def post(self, endpoint: str, data=None, name: str | None = None, headers=None, **kwargs):
        return self._request("POST", endpoint, name, headers, json=data, **kwargs)

    def put(self, endpoint: str, data=None, name: str | None = None, headers=None, **kwargs):
        return self._request("PUT", endpoint, name, headers, json=data, **kwargs)

    def delete(self, endpoint: str, name: str | None = None, headers=None, **kwargs):
        return self._request("DELETE", endpoint, name, headers, **kwargs)

    def _request(self, method: str, endpoint: str, name, headers, **kwargs):
        url = f"{self.osdu_context.host}{endpoint}"
        merged = self.osdu_context.request_headers()
        if headers:
            merged.update(headers)
        override = os.getenv("ADME_BEARER_TOKEN")
        if override:
            merged["Authorization"] = f"Bearer {override}"

        with self.client.request(
            method=method,
            url=url,
            headers=merged,
            name=name,
            catch_response=True,
            **kwargs,
        ) as response:
            if not response.ok:
                response.failure(f"{method} {url} failed with {response.status_code}")
            return response

    # ------------------------------------------------------------------
    # Context + telemetry helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_context(environment: Any) -> RequestContext:
        scenario = os.getenv("TEST_SCENARIO", "")
        parsed_options = getattr(environment, "parsed_options", None)
        if parsed_options is not None and getattr(parsed_options, "scenario", None):
            scenario = parsed_options.scenario
        config = load_config()
        if not scenario:
            scenario = config.run_scenario.scenario or ""
        if not scenario:
            raise ConfigError(
                "No scenario selected. Pass --scenario to the CLI, set "
                "TEST_SCENARIO in the environment, or set "
                "'run_scenario.scenario' in test_config.yaml."
            )
        return RequestContext.from_environment(config, scenario=scenario)

    @staticmethod
    def _print_banner(environment: Any) -> None:
        ctx = PerformanceUser._context
        if ctx is None:
            return
        parsed_options = getattr(environment, "parsed_options", None)

        rows = [
            ("Test Run ID", ctx.test_run_id),
            (
                "Environment",
                "Azure Load Test"
                if os.getenv("AZURE_LOAD_TEST", "").lower() == "true"
                else "Local",
            ),
            ("Host", ctx.host),
            ("Partition", ctx.partition),
            ("App ID", ctx.app_id),
            ("Scenario", ctx.scenario),
            ("Users", getattr(parsed_options, "num_users", "-")),
            ("Spawn rate", getattr(parsed_options, "spawn_rate", "-")),
            ("Run time", getattr(parsed_options, "run_time", "-") or "-"),
        ]
        metadata = ctx.labels()
        if metadata:
            rows.append(("Metadata", ""))
            rows.extend((f"  {k}", v) for k, v in metadata.items())

        key_w = max(len(k) for k, _ in rows)
        val_w = max(len(str(v)) for _, v in rows)
        border = "=" * (key_w + val_w + 7)
        _LOGGER.info(border)
        _LOGGER.info("  OSDU Performance Test — Starting")
        _LOGGER.info(border)
        for key, value in rows:
            _LOGGER.info("  %s : %s", key.ljust(key_w), value)
        _LOGGER.info(border)


# ----------------------------------------------------------------------
# Event listeners at module scope so they are registered on import.
# ----------------------------------------------------------------------
@events.init_command_line_parser.add_listener
def _on_init_parser(parser):
    # Register custom CLI options so Locust auto-renders them as fields
    # under "Custom parameters" in the web-UI swarm form. Defaults pull
    # from current env so headless runs and the UI behave the same.
    parser.add_argument(
        "--osdu-test-name",
        type=str,
        default=os.getenv("OSDU_PERF_TEST_NAME", ""),
        help="osdu_perf test name (overrides OSDU_PERF_TEST_NAME for this run).",
        include_in_web_ui=True,
    )
    parser.add_argument(
        "--osdu-test-run-id-prefix",
        type=str,
        default=os.getenv("OSDU_PERF_TEST_RUN_ID_PREFIX", ""),
        help="osdu_perf test run id prefix (combined as <test-name>-<prefix>-<UTCts>).",
        include_in_web_ui=True,
    )


@events.test_start.add_listener
def _on_test_start(environment, **_kwargs):
    # Apply UI-supplied overrides (if any) by mutating env vars before we
    # rebuild RequestContext. Empty values fall back to whatever the pod
    # was started with.
    opts = getattr(environment, "parsed_options", None)
    if opts is not None:
        ui_test_name = (getattr(opts, "osdu_test_name", "") or "").strip()
        if ui_test_name:
            os.environ["OSDU_PERF_TEST_NAME"] = ui_test_name
        ui_prefix = (getattr(opts, "osdu_test_run_id_prefix", "") or "").strip()
        if ui_prefix:
            os.environ["OSDU_PERF_TEST_RUN_ID_PREFIX"] = ui_prefix

    # Drop any pre-set TEST_RUN_ID so a fresh one is generated for this run
    # using the (possibly UI-overridden) name + prefix + new timestamp.
    for var in ("TEST_RUN_ID_NAME", "TEST_RUN_ID"):
        os.environ.pop(var, None)

    # Reset per-endpoint accumulators and force a fresh RequestContext
    # (with a new test_run_id) so repeat runs in Locust web-UI mode each
    # produce a distinct Kusto entry instead of re-ingesting prior data.
    _events.reset_state()
    PerformanceUser._context = None
    PerformanceUser._banner_printed = False

    # In distributed mode the master runs no Users, so without an
    # explicit build here PerformanceUser._context would stay None and
    # _on_test_stop below would silently skip Kusto ingestion. Build it
    # up-front on everything except workers (which build lazily when
    # the first User instance spawns).
    runner = getattr(environment, "runner", None)
    runner_cls = type(runner).__name__ if runner is not None else ""
    if runner_cls != "WorkerRunner":
        PerformanceUser._context = PerformanceUser._build_context(environment)
        if not PerformanceUser._banner_printed:
            PerformanceUser._print_banner(environment)
            PerformanceUser._banner_printed = True


@events.test_stop.add_listener
def _on_test_stop(environment, **_kwargs):
    ctx = PerformanceUser._context
    if ctx is None:
        _LOGGER.debug("test_stop: no RequestContext — nothing to ingest")
        return
    # In distributed mode, every worker fires test_stop with partial
    # stats and the master fires it with aggregated stats. Ingest only
    # on the master (or local/standalone) so we get exactly one summary
    # row per run.
    runner = getattr(environment, "runner", None)
    runner_cls = type(runner).__name__ if runner is not None else ""
    if runner_cls == "WorkerRunner":
        _LOGGER.debug("test_stop: worker runner — skipping ingestion (master will ingest)")
        return
    kusto_cfg = ctx.config.kusto_export
    if not kusto_cfg.is_configured:
        _LOGGER.info("Kusto not configured — skipping telemetry ingestion")
        return
    try:
        ingestor = KustoIngestor(
            kusto_cfg,
            use_managed_identity=os.getenv("AZURE_LOAD_TEST", "").lower() == "true",
        )
        ingestor.ingest(collect_payload(environment, ctx))
    except Exception as exc:  # pragma: no cover - best-effort
        _LOGGER.error("Kusto ingestion failed: %s", exc)


# ------------------------------------------------------------------
# Distributed mode: forward worker-local request aggregates to master.
# Locust fires `request` only in the process that made the call, so in
# distributed mode the master has no per-endpoint status histogram or
# time-series data unless workers forward it. We piggyback on Locust's
# built-in 3s stats-report channel.
# ------------------------------------------------------------------
@events.report_to_master.add_listener
def _on_report_to_master(client_id, data, **_kwargs):  # noqa: ARG001
    data["osdu_perf_state"] = _events.serialize_state()


@events.worker_report.add_listener
def _on_worker_report(client_id, data, **_kwargs):  # noqa: ARG001
    state = data.pop("osdu_perf_state", None) if isinstance(data, dict) else None
    if state:
        _events.merge_state(state)


__all__ = ["PerformanceUser"]
