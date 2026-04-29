"""Data transfer objects for telemetry reports."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class TestMetadata:
    """Immutable metadata for a single test run."""
    test_run_id: str
    test_scenario: str
    adme_name: str
    partition: str
    performance_tier: str
    version: str
    test_run_environment: str  # "Local" | "Azure Load Test"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    test_duration_seconds: float = 0.0
    max_rps: float = 0.0
    # V3.1 enhanced metadata
    test_name: str = ""
    profile_name: str = ""
    users: int = 0
    spawn_rate: float = 0.0
    run_time_seconds: int = 0
    engine_instances: int = 0
    engine_id: str = ""
    labels: dict = field(default_factory=dict)


@dataclass
class EndpointStat:
    """Per-endpoint metrics collected from Locust stats."""
    name: str
    method: str
    service: str
    requests: int
    failures: int
    median_response_time: float
    average_response_time: float
    min_response_time: float
    max_response_time: float
    percentiles: dict  # {"50th": float, "60th": ..., "999th": float}
    num_none_requests: int
    total_response_time: int
    current_rps: float
    current_fail_per_sec: float
    total_rps: float
    total_fail_per_sec: float
    average_rps: float
    requests_per_sec: float
    failures_per_sec: float
    fail_ratio: float
    avg_content_length: float
    total_content_length: int
    start_time: str
    last_request_timestamp: str
    throughput: float
    # V3.1 status code fields
    status_codes: dict = field(default_factory=dict)
    count_2xx: int = 0
    count_3xx: int = 0
    count_4xx: int = 0
    count_5xx: int = 0
    count_other: int = 0


@dataclass
class ExceptionRecord:
    """Per-error record from Locust stats."""
    method: str
    name: str
    service: str
    error: str
    occurrences: int
    traceback: str
    error_message: str


@dataclass
class TestSummary:
    """Aggregate summary across all endpoints."""
    total_requests: int
    total_failures: int
    median_response_time: float
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    percentiles: dict
    num_none_requests: int
    total_response_time: int
    current_rps: float
    current_fail_per_sec: float
    total_rps: float
    total_fail_per_sec: float
    requests_per_sec: float
    failures_per_sec: float
    fail_ratio: float
    avg_content_length: float
    total_content_length: int
    start_time: str
    end_time: str
    test_duration_seconds: float
    average_rps: float
    throughput: float


@dataclass
class TimeSeriesBucket:
    """One 10-second time bucket for a single endpoint."""
    bucket_start: str
    bucket_duration_seconds: int
    service: str
    name: str
    method: str
    requests: int
    failures: int
    requests_per_sec: float
    failures_per_sec: float
    response_time_50th: float
    response_time_95th: float
    response_time_99th: float


@dataclass
class TestReport:
    """Complete test report passed to every telemetry plugin."""
    metadata: TestMetadata
    endpoint_stats: List[EndpointStat] = field(default_factory=list)
    exceptions: List[ExceptionRecord] = field(default_factory=list)
    summary: Optional[TestSummary] = None
    timeseries: List[TimeSeriesBucket] = field(default_factory=list)
