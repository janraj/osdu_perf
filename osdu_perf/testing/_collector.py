"""Collect Locust stats into a :class:`TelemetryPayload` for Kusto.

All four V2 tables share a common envelope (test id + load-shape) that
makes dashboards composable -- see :mod:`osdu_perf.kusto.schemas` for
the authoritative column list.

The collector is **pure**: it reads ``environment.runner.stats`` + the
per-endpoint status/timeseries accumulators from :mod:`._events` and
returns immutable row dicts. ``test_stop`` in :mod:`.user` is the sole
caller.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from ..kusto import TelemetryPayload
from . import _events
from .context import RequestContext


def collect_payload(environment: Any, ctx: RequestContext) -> TelemetryPayload:
    """Translate ``environment.runner.stats`` into a :class:`TelemetryPayload`."""
    runner = environment.runner
    stats = runner.stats
    now = datetime.now(timezone.utc)

    start_dt = _datetime_from_runner(runner) or _datetime_from_entry(stats.total)
    end_dt = _last_request_dt(stats.total) or now
    duration_s = (end_dt - start_dt).total_seconds() if start_dt else _entry_duration(stats.total)
    if duration_s < 0:
        duration_s = 0.0

    service_override = _collect_service_overrides()
    envelope = _envelope(ctx, now)

    return TelemetryPayload(
        metrics=_metrics_rows(stats, envelope, ctx, service_override),
        exceptions=_exception_rows(stats, envelope, ctx, service_override, now),
        summary=_summary_rows(stats, envelope, start_dt, end_dt, duration_s),
        timeseries=_timeseries_rows(envelope, ctx, service_override),
    )


# ----------------------------------------------------------------------
# Envelope (common columns)
# ----------------------------------------------------------------------
def _envelope(ctx: RequestContext, now: datetime) -> dict[str, Any]:
    explicit = os.getenv("OSDU_PERF_ENV", "").strip()
    if explicit:
        env_label = explicit
    elif os.getenv("AZURE_LOAD_TEST", "").lower() == "true":
        env_label = "Azure Load Test"
    else:
        env_label = "Local"
    return {
        "TestRunId": ctx.test_run_id,
        "ADME": _adme_name(ctx.host),
        "Partition": ctx.partition,
        "TestEnv": env_label,
        "TestScenario": ctx.scenario,
        "TestName": ctx.test_name or ctx.scenario,
        "ProfileName": ctx.profile_name,
        "Users": int(ctx.profile_users or 0),
        "SpawnRate": float(ctx.profile_spawn_rate or 0.0),
        "RunTimeSeconds": int(ctx.profile_run_time_seconds or 0),
        "EngineInstances": int(ctx.profile_engine_instances or 0),
        "EngineId": ctx.engine_id or "",
        "ALTTestRunId": ctx.alt_test_run_id or "",
        "Labels": ctx.labels(),
        "Timestamp": now.isoformat(),
    }


# ----------------------------------------------------------------------
# Metrics (per endpoint)
# ----------------------------------------------------------------------
def _metrics_rows(
    stats: Any,
    envelope: dict[str, Any],
    ctx: RequestContext,
    service_override: str | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in stats.entries.values():
        start_dt = _datetime_from_entry(entry)
        end_dt = _last_request_dt(entry)
        duration = (
            (end_dt - start_dt).total_seconds()
            if start_dt and end_dt and end_dt > start_dt
            else _entry_duration(entry)
        )
        requests_per_sec = entry.num_requests / duration if duration > 0 else 0.0
        failures_per_sec = entry.num_failures / duration if duration > 0 else 0.0
        throughput = entry.total_content_length / duration if duration > 0 else 0.0
        method = str(entry.method or "")
        name = str(entry.name or "")
        status_counts = _events.status_counts_for(method, name)

        row = dict(envelope)
        row.update(
            {
                "Service": _service_name(entry, service_override, ctx),
                "Name": name,
                "Method": method or "UNKNOWN",
                "Requests": int(entry.num_requests),
                "Failures": int(entry.num_failures),
                "RequestsPerSec": requests_per_sec,
                "FailuresPerSec": failures_per_sec,
                "FailRatio": float(getattr(entry, "fail_ratio", 0.0) or 0.0),
                "MedianResponseTime": float(entry.median_response_time),
                "AverageResponseTime": float(entry.avg_response_time),
                "MinResponseTime": float(entry.min_response_time),
                "MaxResponseTime": float(entry.max_response_time),
                "ResponseTime50th": float(entry.get_response_time_percentile(0.5)),
                "ResponseTime60th": float(entry.get_response_time_percentile(0.6)),
                "ResponseTime70th": float(entry.get_response_time_percentile(0.7)),
                "ResponseTime75th": float(entry.get_response_time_percentile(0.75)),
                "ResponseTime80th": float(entry.get_response_time_percentile(0.8)),
                "ResponseTime90th": float(entry.get_response_time_percentile(0.9)),
                "ResponseTime95th": float(entry.get_response_time_percentile(0.95)),
                "ResponseTime98th": float(entry.get_response_time_percentile(0.98)),
                "ResponseTime99th": float(entry.get_response_time_percentile(0.99)),
                "ResponseTime999th": float(entry.get_response_time_percentile(0.999)),
                "TotalContentLength": int(getattr(entry, "total_content_length", 0) or 0),
                "Throughput": throughput,
                "StatusCodes": _events.status_histogram_for(method, name),
                "Count2xx": int(status_counts.get("Count2xx", 0)),
                "Count3xx": int(status_counts.get("Count3xx", 0)),
                "Count4xx": int(status_counts.get("Count4xx", 0)),
                "Count5xx": int(status_counts.get("Count5xx", 0)),
                "CountOther": int(status_counts.get("CountOther", 0)),
                "TestStartTime": start_dt.isoformat() if start_dt else envelope["Timestamp"],
                "LastRequestTimestamp": (
                    end_dt or start_dt or datetime.now(timezone.utc)
                ).isoformat(),
            }
        )
        rows.append(row)
    return rows


# ----------------------------------------------------------------------
# Exceptions (per distinct error)
# ----------------------------------------------------------------------
def _exception_rows(
    stats: Any,
    envelope: dict[str, Any],
    ctx: RequestContext,
    service_override: str | None,
    now: datetime,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    _MAX_TRACEBACK = 4096
    for entry in stats.errors.values():
        name = str(entry.name or "")
        method = str(entry.method or "")
        traceback = str(getattr(entry, "traceback", "") or "")
        row = dict(envelope)
        row.update(
            {
                "Service": _service_name(entry, service_override, ctx),
                "Name": name,
                "Method": method or "UNKNOWN",
                "Error": str(getattr(entry, "error", "Unknown")),
                "ErrorMessage": str(getattr(entry, "msg", "") or ""),
                "Traceback": traceback[:_MAX_TRACEBACK],
                "Occurrences": int(getattr(entry, "occurrences", 0) or 0),
                "FirstSeen": (_first_seen(entry) or now).isoformat(),
                "LastSeen": (_last_seen(entry) or now).isoformat(),
            }
        )
        rows.append(row)
    return rows


# ----------------------------------------------------------------------
# Summary (one row per run)
# ----------------------------------------------------------------------
def _summary_rows(
    stats: Any,
    envelope: dict[str, Any],
    start_dt: datetime | None,
    end_dt: datetime,
    duration_s: float,
) -> list[dict[str, Any]]:
    total = stats.total
    requests_per_sec = total.num_requests / duration_s if duration_s > 0 else 0.0
    failures_per_sec = total.num_failures / duration_s if duration_s > 0 else 0.0
    throughput = total.total_content_length / duration_s if duration_s > 0 else 0.0

    row = dict(envelope)
    row.update(
        {
            "TotalRequests": int(total.num_requests),
            "TotalFailures": int(total.num_failures),
            "RequestsPerSec": requests_per_sec,
            "FailuresPerSec": failures_per_sec,
            "FailRatio": float(getattr(total, "fail_ratio", 0.0) or 0.0),
            "MedianResponseTime": float(total.median_response_time),
            "AvgResponseTime": float(total.avg_response_time),
            "MinResponseTime": float(total.min_response_time),
            "MaxResponseTime": float(total.max_response_time),
            "ResponseTime50th": float(total.get_response_time_percentile(0.5)),
            "ResponseTime60th": float(total.get_response_time_percentile(0.6)),
            "ResponseTime70th": float(total.get_response_time_percentile(0.7)),
            "ResponseTime75th": float(total.get_response_time_percentile(0.75)),
            "ResponseTime80th": float(total.get_response_time_percentile(0.8)),
            "ResponseTime90th": float(total.get_response_time_percentile(0.9)),
            "ResponseTime95th": float(total.get_response_time_percentile(0.95)),
            "ResponseTime98th": float(total.get_response_time_percentile(0.98)),
            "ResponseTime99th": float(total.get_response_time_percentile(0.99)),
            "ResponseTime999th": float(total.get_response_time_percentile(0.999)),
            "TotalContentLength": int(getattr(total, "total_content_length", 0) or 0),
            "Throughput": throughput,
            "TestStartTime": (start_dt or end_dt).isoformat(),
            "TestEndTime": end_dt.isoformat(),
            "TestDurationSeconds": float(duration_s),
        }
    )
    return [row]


# ----------------------------------------------------------------------
# Time series (per 10s bucket per endpoint)
# ----------------------------------------------------------------------
def _timeseries_rows(
    envelope: dict[str, Any],
    ctx: RequestContext,
    service_override: str | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket in _events.drain_timeseries():
        row = dict(envelope)
        row.update(bucket)
        row["Service"] = _service_name_from_name(bucket.get("Name", ""), service_override, ctx)
        rows.append(row)
    return rows


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _adme_name(host: str) -> str:
    try:
        parsed = urlparse(host or "")
        return parsed.hostname or (parsed.netloc.split(":")[0] if parsed.netloc else "unknown")
    except Exception:
        return "unknown"


def _service_name(entry: Any, override: str | None, ctx: RequestContext) -> str:
    if override:
        return override
    return _service_name_from_name(getattr(entry, "name", "") or "", override, ctx)


def _service_name_from_name(name: str, override: str | None, ctx: RequestContext) -> str:
    if override:
        return override
    if name and name.startswith("/"):
        parts = name.split("/")
        if len(parts) > 2 and parts[2]:
            return parts[2]
    return ctx.scenario or "unknown"


def _collect_service_overrides() -> str | None:
    """Discover a ``service_name`` declared on registered BaseService subclasses.

    When there is exactly one subclass loaded with a non-empty class
    attribute, we use it for every row. When there are multiple we
    return None and the per-row logic falls back to URL parsing.
    """
    try:
        from .base_service import BaseService
    except Exception:
        return None
    seen: set[str] = set()
    for cls in _all_subclasses(BaseService):
        value = getattr(cls, "service_name", None)
        if value:
            seen.add(str(value))
    if len(seen) == 1:
        return seen.pop()
    return None


def _all_subclasses(cls: type) -> set[type]:
    collected: set[type] = set()
    stack = list(cls.__subclasses__())
    while stack:
        s = stack.pop()
        if s in collected:
            continue
        collected.add(s)
        stack.extend(s.__subclasses__())
    return collected


def _entry_duration(entry: Any) -> float:
    start = getattr(entry, "start_time", None)
    end = getattr(entry, "last_request_timestamp", None)
    if not start or not end:
        return 0.0
    try:
        delta = float(end) - float(start)
        return delta if delta > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def _datetime_from_runner(runner: Any) -> datetime | None:
    raw = getattr(runner, "start_time", None)
    return _as_datetime(raw)


def _datetime_from_entry(entry: Any) -> datetime | None:
    return _as_datetime(getattr(entry, "start_time", None))


def _last_request_dt(entry: Any) -> datetime | None:
    return _as_datetime(getattr(entry, "last_request_timestamp", None))


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _first_seen(entry: Any) -> datetime | None:
    for attr in ("first_occurrence", "first_seen", "start_time"):
        dt = _as_datetime(getattr(entry, attr, None))
        if dt:
            return dt
    return None


def _last_seen(entry: Any) -> datetime | None:
    for attr in ("last_occurrence", "last_seen", "last_request_timestamp"):
        dt = _as_datetime(getattr(entry, attr, None))
        if dt:
            return dt
    return None


__all__ = ["collect_payload"]
