"""Per-endpoint HTTP status-code aggregator and time-series buckets.

Locust exposes a ``request`` event fired on every completed request. We
hook it once per process, classify the status code into 2xx/3xx/4xx/5xx
buckets, and (optionally) also roll up per-endpoint RPS/latency into
fixed-size time buckets for ``LocustRequestTimeSeriesV2``.

Both collectors are **append-only and thread-safe** so they can be read
at test-stop without coordinating with the locust workers.
"""

from __future__ import annotations

import contextlib
import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_LOCK = threading.Lock()

# keyed by (method, name)
_status_counts: dict[tuple[str, str], dict[str, int]] = defaultdict(
    lambda: {
        "Count2xx": 0,
        "Count3xx": 0,
        "Count4xx": 0,
        "Count5xx": 0,
        "CountOther": 0,
    }
)
_status_histogram: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))


# Time-series buckets -- keyed by (bucket_start_epoch, method, name)
_BUCKET_SECONDS = 10
_bucket_stats: dict[tuple[int, str, str], _BucketAccumulator] = {}


@dataclass
class _BucketAccumulator:
    requests: int = 0
    failures: int = 0
    latencies: list[float] = field(default_factory=list)


def _register() -> None:
    """Hook Locust's ``request`` event. Safe to call multiple times."""
    try:
        from locust import events  # local import so import of this module is cheap
    except Exception:  # pragma: no cover - locust always present at runtime
        return
    if getattr(_register, "_done", False):
        return
    _register._done = True  # type: ignore[attr-defined]

    def _on_request(
        request_type: str,
        name: str,
        response_time: float,
        response_length: int,
        response: Any = None,
        context: Any = None,
        exception: Any = None,
        start_time: float | None = None,
        url: str | None = None,
        **_kwargs: Any,
    ) -> None:
        status = _status_of(response, exception)
        key = (str(request_type or ""), str(name or ""))
        with _LOCK:
            _status_counts[key][_bucket_label(status)] += 1
            if status:
                _status_histogram[key][str(status)] += 1

            # Time-series rollup
            bucket_start = _bucket_of(start_time or time.time())
            acc = _bucket_stats.get((bucket_start, *key))
            if acc is None:
                acc = _BucketAccumulator()
                _bucket_stats[(bucket_start, *key)] = acc
            acc.requests += 1
            if exception is not None:
                acc.failures += 1
            with contextlib.suppress(TypeError, ValueError):
                acc.latencies.append(float(response_time))

    events.request.add_listener(_on_request)


def _status_of(response: Any, exception: Any) -> int | None:
    if exception is not None:
        return None
    code = getattr(response, "status_code", None)
    if code is None:
        return None
    try:
        return int(code)
    except (TypeError, ValueError):
        return None


def _bucket_label(status: int | None) -> str:
    if status is None:
        return "CountOther"
    if 200 <= status < 300:
        return "Count2xx"
    if 300 <= status < 400:
        return "Count3xx"
    if 400 <= status < 500:
        return "Count4xx"
    if 500 <= status < 600:
        return "Count5xx"
    return "CountOther"


def _bucket_of(ts: float) -> int:
    """Floor ``ts`` (unix seconds) to the start of its 10s bucket."""
    return int(math.floor(ts / _BUCKET_SECONDS) * _BUCKET_SECONDS)


def status_counts_for(method: str, name: str) -> dict[str, int]:
    """Return a copy of the 2xx/3xx/4xx/5xx/Other counts for an endpoint."""
    key = (str(method or ""), str(name or ""))
    with _LOCK:
        return dict(_status_counts.get(key, {}))


def status_histogram_for(method: str, name: str) -> dict[str, int]:
    """Return a copy of the per-code histogram (keys are stringified codes)."""
    key = (str(method or ""), str(name or ""))
    with _LOCK:
        return dict(_status_histogram.get(key, {}))


def reset_state() -> None:
    """Clear all per-endpoint accumulators. Called at ``test_start`` so
    repeated runs (e.g. Locust web-UI mode) ingest only the data from the
    most recent run."""
    with _LOCK:
        _status_counts.clear()
        _status_histogram.clear()
        _bucket_stats.clear()


def drain_timeseries(now_epoch: float | None = None) -> list[dict[str, Any]]:
    """Return per-bucket roll-ups keyed by (BucketStart, Method, Name).

    ``now_epoch`` is accepted only for tests; by default the current
    time is used. The function does **not** clear state so a second call
    returns the same buckets (test_stop is the only expected caller).
    """
    rows: list[dict[str, Any]] = []
    with _LOCK:
        for (bucket_start, method, name), acc in _bucket_stats.items():
            if acc.requests == 0:
                continue
            latencies = sorted(acc.latencies)
            rows.append(
                {
                    "BucketStart": datetime.fromtimestamp(
                        bucket_start, tz=timezone.utc
                    ).isoformat(),
                    "BucketDurationSeconds": _BUCKET_SECONDS,
                    "Method": method,
                    "Name": name,
                    "Requests": acc.requests,
                    "Failures": acc.failures,
                    "RequestsPerSec": acc.requests / _BUCKET_SECONDS,
                    "FailuresPerSec": acc.failures / _BUCKET_SECONDS,
                    "ResponseTime50th": _pct(latencies, 0.50),
                    "ResponseTime95th": _pct(latencies, 0.95),
                    "ResponseTime99th": _pct(latencies, 0.99),
                }
            )
    rows.sort(key=lambda r: (r["BucketStart"], r["Name"]))
    return rows


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    idx = min(len(values) - 1, int(round(q * (len(values) - 1))))
    return float(values[idx])


__all__ = [
    "_register",
    "status_counts_for",
    "status_histogram_for",
    "drain_timeseries",
]
