"""Per-request event collector — status codes + 10s time-series buckets.

Hooks Locust's ``events.request`` to collect data NOT available from
Locust's built-in ``StatsEntry``:
  * HTTP status-code distribution (Locust only tracks success/failure)
  * Time-bucketed request/latency data for trend analysis
"""

import math
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

_BUCKET_SECONDS = 10

# ──────────────────────────────────────────────────────────────
# Internal accumulators
# ──────────────────────────────────────────────────────────────

_LOCK = threading.Lock()

# keyed by (method, name) → {"Count2xx": N, "Count3xx": N, …}
_status_counts: dict[tuple[str, str], dict[str, int]] = {}

# keyed by (method, name) → {"200": N, "404": M, …}
_status_histogram: dict[tuple[str, str], dict[str, int]] = {}


@dataclass
class _BucketAccumulator:
    requests: int = 0
    failures: int = 0
    latencies: list[float] = field(default_factory=list)


# keyed by (bucket_start_epoch, method, name)
_bucket_stats: dict[tuple[int, str, str], _BucketAccumulator] = {}

_registered = False

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _bucket_of(ts: float) -> int:
    """Floor unix timestamp to start of its 10-second bucket."""
    return int(math.floor(ts / _BUCKET_SECONDS) * _BUCKET_SECONDS)


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


def _status_of(response, exception) -> int | None:
    if response is not None:
        code = getattr(response, "status_code", None)
        if code is not None:
            return int(code)
    return None


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f = int(math.floor(k))
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])


# ──────────────────────────────────────────────────────────────
# Event handler
# ──────────────────────────────────────────────────────────────


def _on_request(request_type, name, response_time, response_length,
                response=None, exception=None, start_time=None, **kwargs):
    status = _status_of(response, exception)
    key = (str(request_type), str(name))

    with _LOCK:
        # 1. Status code classification
        if key not in _status_counts:
            _status_counts[key] = {}
        label = _bucket_label(status)
        _status_counts[key][label] = _status_counts[key].get(label, 0) + 1

        if status is not None:
            if key not in _status_histogram:
                _status_histogram[key] = {}
            s = str(status)
            _status_histogram[key][s] = _status_histogram[key].get(s, 0) + 1

        # 2. Time-series bucket accumulation
        bucket_start = _bucket_of(start_time or time.time())
        bkey = (bucket_start, *key)
        if bkey not in _bucket_stats:
            _bucket_stats[bkey] = _BucketAccumulator()
        acc = _bucket_stats[bkey]
        acc.requests += 1
        if exception is not None:
            acc.failures += 1
        if response_time is not None:
            acc.latencies.append(float(response_time))


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────


def register():
    """Hook ``events.request`` listener (idempotent)."""
    global _registered
    if _registered:
        return
    try:
        from locust import events as locust_events
        locust_events.request.add_listener(_on_request)
        _registered = True
    except ImportError:
        pass


def status_counts_for(method: str, name: str) -> dict[str, int]:
    """Returns ``{"Count2xx": N, ...}`` for an endpoint."""
    with _LOCK:
        return dict(_status_counts.get((method, name), {}))


def status_histogram_for(method: str, name: str) -> dict[str, int]:
    """Returns ``{"200": N, "404": M, ...}`` for an endpoint."""
    with _LOCK:
        return dict(_status_histogram.get((method, name), {}))


def drain_timeseries() -> list[dict]:
    """Returns list of bucket row dicts with computed percentiles.

    Does NOT clear state — call ``reset_state()`` separately.
    """
    with _LOCK:
        rows = []
        for (bucket_epoch, method, name), acc in sorted(_bucket_stats.items()):
            sorted_lat = sorted(acc.latencies)
            rows.append({
                "BucketStart": datetime.fromtimestamp(bucket_epoch, tz=timezone.utc).isoformat(),
                "BucketDurationSeconds": _BUCKET_SECONDS,
                "Method": method,
                "Name": name,
                "Requests": acc.requests,
                "Failures": acc.failures,
                "RequestsPerSec": round(acc.requests / _BUCKET_SECONDS, 2),
                "FailuresPerSec": round(acc.failures / _BUCKET_SECONDS, 2),
                "ResponseTime50th": round(_percentile(sorted_lat, 0.50), 2),
                "ResponseTime95th": round(_percentile(sorted_lat, 0.95), 2),
                "ResponseTime99th": round(_percentile(sorted_lat, 0.99), 2),
            })
        return rows


def serialize_state() -> dict:
    """Snapshot + clear all accumulators (for worker → master forwarding)."""
    with _LOCK:
        state = {
            "status_counts": {f"{m}|{n}": dict(v) for (m, n), v in _status_counts.items()},
            "status_histogram": {f"{m}|{n}": dict(v) for (m, n), v in _status_histogram.items()},
            "buckets": {
                f"{b}|{m}|{n}": {"requests": a.requests, "failures": a.failures, "latencies": list(a.latencies)}
                for (b, m, n), a in _bucket_stats.items()
            },
        }
        _status_counts.clear()
        _status_histogram.clear()
        _bucket_stats.clear()
        return state


def merge_state(state: dict | None) -> None:
    """Merge a worker's state dict into master accumulators."""
    if not state:
        return
    with _LOCK:
        for composite_key, counts in state.get("status_counts", {}).items():
            m, n = composite_key.split("|", 1)
            key = (m, n)
            if key not in _status_counts:
                _status_counts[key] = {}
            for label, val in counts.items():
                _status_counts[key][label] = _status_counts[key].get(label, 0) + val

        for composite_key, hist in state.get("status_histogram", {}).items():
            m, n = composite_key.split("|", 1)
            key = (m, n)
            if key not in _status_histogram:
                _status_histogram[key] = {}
            for code, val in hist.items():
                _status_histogram[key][code] = _status_histogram[key].get(code, 0) + val

        for composite_key, bdata in state.get("buckets", {}).items():
            parts = composite_key.split("|", 2)
            bkey = (int(parts[0]), parts[1], parts[2])
            if bkey not in _bucket_stats:
                _bucket_stats[bkey] = _BucketAccumulator()
            acc = _bucket_stats[bkey]
            acc.requests += bdata["requests"]
            acc.failures += bdata["failures"]
            acc.latencies.extend(bdata["latencies"])


def reset_state() -> None:
    """Clear all accumulators (called at ``test_start`` for web-UI reruns)."""
    with _LOCK:
        _status_counts.clear()
        _status_histogram.clear()
        _bucket_stats.clear()
