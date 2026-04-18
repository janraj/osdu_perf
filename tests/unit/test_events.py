"""Tests for the per-endpoint status/time-series accumulators."""

from __future__ import annotations

from osdu_perf.testing import _events


def _reset_state() -> None:
    _events._status_counts.clear()
    _events._status_histogram.clear()
    _events._bucket_stats.clear()


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _invoke(
    status_code: int | None,
    *,
    method: str = "POST",
    name: str = "search_query",
    response_time: float = 100.0,
    exception: Exception | None = None,
    start_time: float | None = 1_700_000_000.0,
) -> None:
    """Simulate Locust's ``request`` event without touching the real hook."""
    from osdu_perf.testing._events import (  # noqa: PLC0415
        _LOCK,
        _bucket_label,
        _bucket_of,
        _bucket_stats,
        _BucketAccumulator,
        _status_counts,
        _status_histogram,
        _status_of,
    )

    response = _FakeResponse(status_code) if status_code is not None else None
    status = _status_of(response, exception)
    key = (method, name)
    with _LOCK:
        _status_counts[key][_bucket_label(status)] += 1
        if status:
            _status_histogram[key][str(status)] += 1
        bucket_start = _bucket_of(start_time or 0.0)
        acc = _bucket_stats.get((bucket_start, *key))
        if acc is None:
            acc = _BucketAccumulator()
            _bucket_stats[(bucket_start, *key)] = acc
        acc.requests += 1
        if exception is not None:
            acc.failures += 1
        acc.latencies.append(float(response_time))


def test_status_counts_group_by_class() -> None:
    _reset_state()
    for code in (200, 201, 204):
        _invoke(code)
    for code in (301, 302):
        _invoke(code)
    _invoke(404)
    _invoke(500)
    _invoke(None, exception=RuntimeError("boom"))

    counts = _events.status_counts_for("POST", "search_query")
    assert counts == {
        "Count2xx": 3,
        "Count3xx": 2,
        "Count4xx": 1,
        "Count5xx": 1,
        "CountOther": 1,
    }


def test_status_histogram_tracks_each_code() -> None:
    _reset_state()
    _invoke(200)
    _invoke(200)
    _invoke(401)

    histogram = _events.status_histogram_for("POST", "search_query")
    assert histogram == {"200": 2, "401": 1}


def test_status_counts_isolate_endpoints() -> None:
    _reset_state()
    _invoke(200, name="search")
    _invoke(500, name="delete")

    assert _events.status_counts_for("POST", "search")["Count2xx"] == 1
    assert _events.status_counts_for("POST", "delete")["Count5xx"] == 1
    assert _events.status_counts_for("POST", "search")["Count5xx"] == 0


def test_drain_timeseries_groups_by_10s_bucket() -> None:
    _reset_state()
    # two requests in bucket 1_700_000_000, one in next bucket
    _invoke(200, start_time=1_700_000_000.0, response_time=100.0)
    _invoke(200, start_time=1_700_000_005.0, response_time=300.0)
    _invoke(500, start_time=1_700_000_015.0, response_time=200.0)

    rows = _events.drain_timeseries()
    assert len(rows) == 2
    first, second = rows[0], rows[1]
    assert first["Requests"] == 2
    assert first["Failures"] == 0
    assert first["BucketDurationSeconds"] == 10
    assert first["ResponseTime50th"] > 0
    assert second["Requests"] == 1
    assert second["Failures"] == 0  # 500 is not an exception


def test_drain_timeseries_counts_exceptions_as_failures() -> None:
    _reset_state()
    _invoke(None, exception=ValueError("x"), start_time=1_700_000_000.0)

    rows = _events.drain_timeseries()
    assert rows[0]["Requests"] == 1
    assert rows[0]["Failures"] == 1


def test_drain_timeseries_skips_empty_buckets() -> None:
    _reset_state()
    rows = _events.drain_timeseries()
    assert rows == []


def test_pct_handles_empty_and_single_value() -> None:
    assert _events._pct([], 0.95) == 0.0
    assert _events._pct([42.0], 0.99) == 42.0
    assert _events._pct([1.0, 2.0, 3.0, 4.0, 5.0], 0.5) in (3.0, 3.0)
