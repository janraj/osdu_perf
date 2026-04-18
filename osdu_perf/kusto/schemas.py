"""Kusto table names, column DDL, and provisioning statements."""

from __future__ import annotations

METRICS_TABLE = "LocustMetricsV2"
EXCEPTIONS_TABLE = "LocustExceptionsV2"
SUMMARY_TABLE = "LocustTestSummaryV2"
TIMESERIES_TABLE = "LocustRequestTimeSeriesV2"

ALL_TABLES = (METRICS_TABLE, EXCEPTIONS_TABLE, SUMMARY_TABLE, TIMESERIES_TABLE)


_COMMON_COLUMNS: tuple[tuple[str, str], ...] = (
    ("TestRunId", "string"),
    ("ADME", "string"),
    ("Partition", "string"),
    ("TestEnv", "string"),
    ("TestScenario", "string"),
    ("TestName", "string"),
    ("ProfileName", "string"),
    ("Users", "int"),
    ("SpawnRate", "real"),
    ("RunTimeSeconds", "int"),
    ("EngineInstances", "int"),
    ("EngineId", "string"),
    ("ALTTestRunId", "string"),
    ("Labels", "dynamic"),
    ("Timestamp", "datetime"),
)


_METRICS_COLUMNS: tuple[tuple[str, str], ...] = _COMMON_COLUMNS + (
    ("Service", "string"),
    ("Name", "string"),
    ("Method", "string"),
    ("Requests", "long"),
    ("Failures", "long"),
    ("RequestsPerSec", "real"),
    ("FailuresPerSec", "real"),
    ("FailRatio", "real"),
    ("MedianResponseTime", "real"),
    ("AverageResponseTime", "real"),
    ("MinResponseTime", "real"),
    ("MaxResponseTime", "real"),
    ("ResponseTime50th", "real"),
    ("ResponseTime60th", "real"),
    ("ResponseTime70th", "real"),
    ("ResponseTime75th", "real"),
    ("ResponseTime80th", "real"),
    ("ResponseTime90th", "real"),
    ("ResponseTime95th", "real"),
    ("ResponseTime98th", "real"),
    ("ResponseTime99th", "real"),
    ("ResponseTime999th", "real"),
    ("TotalContentLength", "long"),
    ("Throughput", "real"),
    ("StatusCodes", "dynamic"),
    ("Count2xx", "long"),
    ("Count3xx", "long"),
    ("Count4xx", "long"),
    ("Count5xx", "long"),
    ("CountOther", "long"),
    ("TestStartTime", "datetime"),
    ("LastRequestTimestamp", "datetime"),
)


_SUMMARY_COLUMNS: tuple[tuple[str, str], ...] = _COMMON_COLUMNS + (
    ("TotalRequests", "long"),
    ("TotalFailures", "long"),
    ("RequestsPerSec", "real"),
    ("FailuresPerSec", "real"),
    ("FailRatio", "real"),
    ("MedianResponseTime", "real"),
    ("AvgResponseTime", "real"),
    ("MinResponseTime", "real"),
    ("MaxResponseTime", "real"),
    ("ResponseTime50th", "real"),
    ("ResponseTime60th", "real"),
    ("ResponseTime70th", "real"),
    ("ResponseTime75th", "real"),
    ("ResponseTime80th", "real"),
    ("ResponseTime90th", "real"),
    ("ResponseTime95th", "real"),
    ("ResponseTime98th", "real"),
    ("ResponseTime99th", "real"),
    ("ResponseTime999th", "real"),
    ("TotalContentLength", "long"),
    ("Throughput", "real"),
    ("TestStartTime", "datetime"),
    ("TestEndTime", "datetime"),
    ("TestDurationSeconds", "real"),
)


_EXCEPTIONS_COLUMNS: tuple[tuple[str, str], ...] = _COMMON_COLUMNS + (
    ("Service", "string"),
    ("Name", "string"),
    ("Method", "string"),
    ("Error", "string"),
    ("ErrorMessage", "string"),
    ("Traceback", "string"),
    ("Occurrences", "long"),
    ("FirstSeen", "datetime"),
    ("LastSeen", "datetime"),
)


_TIMESERIES_COLUMNS: tuple[tuple[str, str], ...] = _COMMON_COLUMNS + (
    ("BucketStart", "datetime"),
    ("BucketDurationSeconds", "int"),
    ("Service", "string"),
    ("Name", "string"),
    ("Method", "string"),
    ("Requests", "long"),
    ("Failures", "long"),
    ("RequestsPerSec", "real"),
    ("FailuresPerSec", "real"),
    ("ResponseTime50th", "real"),
    ("ResponseTime95th", "real"),
    ("ResponseTime99th", "real"),
)


TABLE_SCHEMAS: dict[str, tuple[tuple[str, str], ...]] = {
    METRICS_TABLE: _METRICS_COLUMNS,
    SUMMARY_TABLE: _SUMMARY_COLUMNS,
    EXCEPTIONS_TABLE: _EXCEPTIONS_COLUMNS,
    TIMESERIES_TABLE: _TIMESERIES_COLUMNS,
}


def columns_for(table: str) -> tuple[tuple[str, str], ...]:
    return TABLE_SCHEMAS[table]


def build_provisioning_script() -> list[str]:
    commands: list[str] = []
    for table, cols in TABLE_SCHEMAS.items():
        col_spec = ", ".join(f"{name}:{ktype}" for name, ktype in cols)
        commands.append(f".create-merge table {table} ({col_spec})")
        commands.append(f".alter-merge table {table} ({col_spec})")
        mapping = ", ".join(f'{{"column":"{name}","path":"$.{name}"}}' for name, _ in cols)
        commands.append(
            f".create-or-alter table {table} ingestion json mapping "
            f"\"{table}_mapping\" '[{mapping}]'"
        )
    return commands


__all__ = [
    "METRICS_TABLE",
    "EXCEPTIONS_TABLE",
    "SUMMARY_TABLE",
    "TIMESERIES_TABLE",
    "ALL_TABLES",
    "TABLE_SCHEMAS",
    "columns_for",
    "build_provisioning_script",
]
