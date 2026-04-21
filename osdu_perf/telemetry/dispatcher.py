"""Telemetry dispatcher — builds TestReport from Locust stats and fans out to plugins."""

import os
import uuid
import logging
from datetime import datetime
from urllib.parse import urlparse
from typing import List

from .plugin_base import TelemetryPlugin
from .report import (
    TestReport, TestMetadata, EndpointStat,
    ExceptionRecord, TestSummary,
)

logger = logging.getLogger(__name__)


def _get_adme_name(host: str) -> str:
    try:
        parsed = urlparse(host)
        return parsed.hostname or parsed.netloc.split(':')[0]
    except Exception:
        return "unknown"


def _get_service_name(url_path: str) -> str:
    try:
        parsed = urlparse(url_path)
        return parsed.path.split('/')[2] or "unknown"
    except Exception:
        return "unknown"


def _safe_float(obj, attr, default=0.0):
    val = getattr(obj, attr, None)
    return float(val) if val is not None else default


def _safe_int(obj, attr, default=0):
    val = getattr(obj, attr, None)
    return int(val) if val is not None else default


def _get_reqs_per_sec(entry) -> float:
    raw = getattr(entry, 'num_reqs_per_sec', 0)
    if hasattr(raw, 'get'):
        return float(raw.get('total', 0))
    return float(raw)


def _get_fail_per_sec(entry) -> float:
    raw = getattr(entry, 'num_fail_per_sec', 0)
    if hasattr(raw, 'get'):
        return float(raw.get('total', 0))
    return float(raw)


PERCENTILE_KEYS = [
    ("50th", 0.5), ("60th", 0.6), ("70th", 0.7), ("80th", 0.8),
    ("90th", 0.9), ("95th", 0.95), ("98th", 0.98), ("99th", 0.99),
    ("999th", 0.999), ("9999th", 0.9999), ("100th", 1.0),
]


def _collect_percentiles(entry) -> dict:
    return {label: entry.get_response_time_percentile(p) for label, p in PERCENTILE_KEYS}


class TelemetryDispatcher:
    """Builds a TestReport from Locust stats and dispatches to enabled plugins."""

    def __init__(self, plugins: List[TelemetryPlugin], config: dict):
        self._plugins = [p for p in plugins if p.is_enabled(config)]
        self._config = config

    def dispatch(self, environment, input_handler) -> None:
        if not self._plugins:
            logger.info("No telemetry plugins enabled, skipping metrics push")
            return

        plugin_names = [p.name() for p in self._plugins]
        logger.info(f"Enabled plugins: {plugin_names}")

        try:
            report = self._build_report(environment, input_handler)
        except Exception:
            logger.error("Failed to build telemetry report", exc_info=True)
            return

        if report.summary:
            logger.info(
                f"TestReport built: {len(report.endpoint_stats)} endpoints, "
                f"{len(report.exceptions)} errors, "
                f"duration={report.summary.test_duration_seconds:.1f}s, "
                f"total_requests={report.summary.total_requests}"
            )
        else:
            logger.info(
                f"TestReport built: {len(report.endpoint_stats)} endpoints, "
                f"{len(report.exceptions)} errors, no summary"
            )

        failed = []
        for plugin in self._plugins:
            try:
                plugin.publish(report)
                logger.info(f"Telemetry plugin '{plugin.name()}' completed successfully")
            except Exception:
                logger.error(f"Telemetry plugin '{plugin.name()}' failed — metrics NOT sent", exc_info=True)
                failed.append(plugin.name())

        if failed:
            logger.info("Test run completed (telemetry errors do not affect test status)")
        else:
            logger.info("All plugins completed successfully")

    # ------------------------------------------------------------------
    # Report building — migrated from PerformanceUser.on_test_stop
    # ------------------------------------------------------------------

    def _build_report(self, environment, input_handler) -> TestReport:
        current_timestamp = datetime.utcnow()

        # Metadata
        test_run_id = os.getenv("TEST_RUN_ID_NAME") or os.getenv("TEST_RUN_ID")
        if not test_run_id:
            test_run_id = str(uuid.uuid4())
            logger.warning(f"TEST_RUN_ID not found in environment, using fallback: {test_run_id}")

        is_azure = os.getenv("AZURE_LOAD_TEST", "").lower() == "true"
        test_run_environment = "Azure Load Test" if is_azure else "Local"

        adme = _get_adme_name(environment.host)
        partition = input_handler.partition if input_handler else os.getenv("PARTITION", "Unknown")
        performance_tier = (
            input_handler.get_osdu_performance_tier(os.getenv("PERFORMANCE_TIER", os.getenv("SKU", None)))
            if input_handler else os.getenv("PERFORMANCE_TIER", os.getenv("SKU", "Unknown"))
        )
        version = (
            input_handler.get_osdu_version(os.getenv("VERSION", None))
            if input_handler else os.getenv("VERSION", "Unknown")
        )
        test_scenario = (
            input_handler.get_test_scenario(os.getenv("LOCUST_TAGS", None))
            if input_handler else os.getenv("LOCUST_TAGS", "Unknown")
        )

        stats = environment.runner.stats
        start_time = getattr(environment.runner, 'start_time', None)
        try:
            if start_time:
                test_duration = (current_timestamp - start_time).total_seconds()
                max_rps = stats.total.num_requests / test_duration if test_duration > 0 else 0
            else:
                test_duration = 0
                max_rps = 0
        except Exception:
            test_duration = 0
            max_rps = 0

        metadata = TestMetadata(
            test_run_id=test_run_id,
            test_scenario=test_scenario,
            adme_name=adme,
            partition=partition,
            performance_tier=performance_tier,
            version=version,
            test_run_environment=test_run_environment,
            timestamp=current_timestamp,
            test_duration_seconds=test_duration,
            max_rps=max_rps,
        )

        # Endpoint stats
        endpoint_stats = []
        for entry in stats.entries.values():
            service = _get_service_name(entry.name)
            entry_start = (
                datetime.fromtimestamp(entry.start_time).isoformat()
                if hasattr(entry, 'start_time') and entry.start_time is not None
                else current_timestamp.isoformat()
            )
            entry_end = (
                datetime.fromtimestamp(entry.last_request_timestamp).isoformat()
                if hasattr(entry, 'last_request_timestamp') and entry.last_request_timestamp is not None
                else current_timestamp.isoformat()
            )
            start_dt = datetime.fromisoformat(entry_start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(entry_end.replace("Z", "+00:00"))
            duration = (end_dt - start_dt).total_seconds()
            throughput = (entry.total_content_length / duration) if duration > 0 else 0
            average_rps = (entry.num_requests / duration) if duration > 0 else 0

            endpoint_stats.append(EndpointStat(
                name=entry.name,
                method=entry.method,
                service=service,
                requests=entry.num_requests,
                failures=entry.num_failures,
                num_none_requests=_safe_int(entry, 'num_none_requests'),
                total_response_time=_safe_int(entry, 'total_response_time'),
                median_response_time=entry.median_response_time,
                average_response_time=entry.avg_response_time,
                min_response_time=entry.min_response_time,
                max_response_time=entry.max_response_time,
                percentiles=_collect_percentiles(entry),
                current_rps=_safe_float(entry, 'current_rps'),
                current_fail_per_sec=_safe_float(entry, 'current_fail_per_sec'),
                total_rps=_safe_float(entry, 'total_rps'),
                total_fail_per_sec=_safe_float(entry, 'total_fail_per_sec'),
                average_rps=average_rps,
                requests_per_sec=_get_reqs_per_sec(entry),
                failures_per_sec=_get_fail_per_sec(entry),
                fail_ratio=_safe_float(entry, 'fail_ratio'),
                avg_content_length=_safe_float(entry, 'avg_content_length'),
                total_content_length=_safe_int(entry, 'total_content_length'),
                start_time=entry_start,
                last_request_timestamp=entry_end,
                throughput=throughput,
            ))

        # Exceptions
        exceptions = []
        for _key, error_entry in stats.errors.items():
            exceptions.append(ExceptionRecord(
                method=str(error_entry.method),
                name=str(error_entry.name),
                service=_get_service_name(str(error_entry.name)),
                error=str(error_entry.error) if hasattr(error_entry, 'error') else "Unknown",
                occurrences=int(error_entry.occurrences) if hasattr(error_entry, 'occurrences') else 0,
                traceback=str(getattr(error_entry, 'traceback', '')),
                error_message=str(getattr(error_entry, 'msg', '')),
            ))

        # Summary
        total_throughput = (stats.total.total_content_length / test_duration) if test_duration > 0 else 0
        total_avg_rps = (stats.total.num_requests / test_duration) if test_duration > 0 else 0
        summary = TestSummary(
            total_requests=int(stats.total.num_requests),
            total_failures=int(stats.total.num_failures),
            num_none_requests=_safe_int(stats.total, 'num_none_requests'),
            total_response_time=_safe_int(stats.total, 'total_response_time'),
            median_response_time=float(stats.total.median_response_time),
            avg_response_time=float(stats.total.avg_response_time),
            min_response_time=float(stats.total.min_response_time),
            max_response_time=float(stats.total.max_response_time),
            percentiles=_collect_percentiles(stats.total),
            current_rps=_safe_float(stats.total, 'current_rps'),
            current_fail_per_sec=_safe_float(stats.total, 'current_fail_per_sec'),
            total_rps=_safe_float(stats.total, 'total_rps'),
            total_fail_per_sec=_safe_float(stats.total, 'total_fail_per_sec'),
            requests_per_sec=_get_reqs_per_sec(stats.total),
            failures_per_sec=_get_fail_per_sec(stats.total),
            fail_ratio=_safe_float(stats.total, 'fail_ratio'),
            avg_content_length=_safe_float(stats.total, 'avg_content_length'),
            total_content_length=_safe_int(stats.total, 'total_content_length'),
            start_time=start_time.isoformat() if start_time and hasattr(start_time, 'isoformat') else current_timestamp.isoformat(),
            end_time=current_timestamp.isoformat(),
            test_duration_seconds=float(test_duration),
            average_rps=float(total_avg_rps),
            throughput=total_throughput,
        )

        logger.info(f"Test Run ID: {test_run_id}")
        return TestReport(
            metadata=metadata,
            endpoint_stats=endpoint_stats,
            exceptions=exceptions,
            summary=summary,
        )
