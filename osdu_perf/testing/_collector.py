"""Collect Locust stats into a :class:`TelemetryPayload` for Kusto."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from ..kusto import TelemetryPayload
from .context import RequestContext


def collect_payload(environment: Any, ctx: RequestContext) -> TelemetryPayload:
    """Translate ``environment.runner.stats`` into a :class:`TelemetryPayload`."""
    runner = environment.runner
    stats = runner.stats

    now = datetime.utcnow()
    start_time = getattr(runner, "start_time", None)
    total_duration_s = (now - start_time).total_seconds() if start_time else 0.0

    env_label = "Azure Load Test" if os.getenv("AZURE_LOAD_TEST", "").lower() == "true" else "Local"
    adme = _adme_name(environment.host)
    metadata = ctx.test_metadata()

    common = {
        "TestRunId": ctx.test_run_id,
        "ADME": adme,
        "Partition": ctx.partition,
        "TestEnv": env_label,
        "TestScenario": ctx.scenario,
        "Metadata": metadata,
    }

    return TelemetryPayload(
        metrics=_metrics_rows(stats, common, now),
        exceptions=_exception_rows(stats, common, now),
        summary=_summary_rows(stats, common, now, total_duration_s, start_time),
    )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _adme_name(host: str) -> str:
    try:
        parsed = urlparse(host or "")
        return parsed.hostname or (parsed.netloc.split(":")[0] if parsed.netloc else "unknown")
    except Exception:
        return "unknown"


def _service_name(url_path: str) -> str:
    try:
        parsed = urlparse(url_path)
        parts = parsed.path.split("/")
        return parts[2] if len(parts) > 2 else "unknown"
    except Exception:
        return "unknown"


def _metrics_rows(
    stats: Any, common: dict[str, Any], now: datetime
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in stats.entries.values():
        start_iso = _iso(getattr(entry, "start_time", None)) or now.isoformat()
        end_iso = _iso(getattr(entry, "last_request_timestamp", None)) or now.isoformat()
        duration = max(
            (datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
             - datetime.fromisoformat(start_iso.replace("Z", "+00:00"))).total_seconds(),
            0.0,
        )
        average_rps = entry.num_requests / duration if duration > 0 else 0.0
        throughput = entry.total_content_length / duration if duration > 0 else 0.0

        row = dict(common)
        row.update(
            {
                "Service": _service_name(entry.name),
                "Name": entry.name,
                "Method": entry.method,
                "Requests": entry.num_requests,
                "Failures": entry.num_failures,
                "MedianResponseTime": entry.median_response_time,
                "AverageResponseTime": entry.avg_response_time,
                "MinResponseTime": entry.min_response_time,
                "MaxResponseTime": entry.max_response_time,
                "ResponseTime50th": entry.get_response_time_percentile(0.5),
                "ResponseTime60th": entry.get_response_time_percentile(0.6),
                "ResponseTime70th": entry.get_response_time_percentile(0.7),
                "ResponseTime80th": entry.get_response_time_percentile(0.8),
                "ResponseTime90th": entry.get_response_time_percentile(0.9),
                "ResponseTime95th": entry.get_response_time_percentile(0.95),
                "ResponseTime98th": entry.get_response_time_percentile(0.98),
                "ResponseTime99th": entry.get_response_time_percentile(0.99),
                "ResponseTime999th": entry.get_response_time_percentile(0.999),
                "CurrentRPS": float(getattr(entry, "current_rps", 0.0) or 0.0),
                "CurrentFailPerSec": float(getattr(entry, "current_fail_per_sec", 0.0) or 0.0),
                "AverageRPS": average_rps,
                "FailRatio": float(getattr(entry, "fail_ratio", 0.0) or 0.0),
                "TotalContentLength": int(getattr(entry, "total_content_length", 0) or 0),
                "StartTime": start_iso,
                "LastRequestTimestamp": end_iso,
                "Timestamp": now.isoformat(),
                "Throughput": throughput,
            }
        )
        rows.append(row)
    return rows


def _exception_rows(
    stats: Any, common: dict[str, Any], now: datetime
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in stats.errors.values():
        name = str(entry.name)
        row = dict(common)
        row.update(
            {
                "Method": str(entry.method),
                "Name": name,
                "Service": _service_name(name),
                "Error": str(getattr(entry, "error", "Unknown")),
                "Occurrences": int(getattr(entry, "occurrences", 0) or 0),
                "Traceback": str(getattr(entry, "traceback", "")),
                "ErrorMessage": str(getattr(entry, "msg", "")),
                "Timestamp": now.isoformat(),
            }
        )
        rows.append(row)
    return rows


def _summary_rows(
    stats: Any,
    common: dict[str, Any],
    now: datetime,
    duration_s: float,
    start_time: Any,
) -> list[dict[str, Any]]:
    total = stats.total
    average_rps = total.num_requests / duration_s if duration_s > 0 else 0.0
    throughput = total.total_content_length / duration_s if duration_s > 0 else 0.0

    row = dict(common)
    row.update(
        {
            "TotalRequests": int(total.num_requests),
            "TotalFailures": int(total.num_failures),
            "MedianResponseTime": float(total.median_response_time),
            "AvgResponseTime": float(total.avg_response_time),
            "MinResponseTime": float(total.min_response_time),
            "MaxResponseTime": float(total.max_response_time),
            "ResponseTime50th": float(total.get_response_time_percentile(0.5)),
            "ResponseTime60th": float(total.get_response_time_percentile(0.6)),
            "ResponseTime70th": float(total.get_response_time_percentile(0.7)),
            "ResponseTime80th": float(total.get_response_time_percentile(0.8)),
            "ResponseTime90th": float(total.get_response_time_percentile(0.9)),
            "ResponseTime95th": float(total.get_response_time_percentile(0.95)),
            "ResponseTime98th": float(total.get_response_time_percentile(0.98)),
            "ResponseTime99th": float(total.get_response_time_percentile(0.99)),
            "ResponseTime999th": float(total.get_response_time_percentile(0.999)),
            "CurrentRPS": float(getattr(total, "current_rps", 0.0) or 0.0),
            "CurrentFailPerSec": float(getattr(total, "current_fail_per_sec", 0.0) or 0.0),
            "AverageRPS": average_rps,
            "FailRatio": float(getattr(total, "fail_ratio", 0.0) or 0.0),
            "TotalContentLength": int(getattr(total, "total_content_length", 0) or 0),
            "StartTime": start_time.isoformat() if start_time else now.isoformat(),
            "EndTime": now.isoformat(),
            "TestDurationSeconds": float(duration_s),
            "Throughput": throughput,
            "Timestamp": now.isoformat(),
        }
    )
    return [row]


def _iso(ts: Any) -> str | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts)).isoformat()
    except (TypeError, ValueError):
        return None


__all__ = ["collect_payload"]
