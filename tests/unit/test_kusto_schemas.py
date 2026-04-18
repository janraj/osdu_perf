"""Tests for the V2 Kusto schema module."""

from osdu_perf.kusto.schemas import (
    ALL_TABLES,
    EXCEPTIONS_TABLE,
    METRICS_TABLE,
    SUMMARY_TABLE,
    TABLE_SCHEMAS,
    TIMESERIES_TABLE,
    build_provisioning_script,
    columns_for,
)

_COMMON = {
    "TestRunId",
    "ADME",
    "Partition",
    "TestEnv",
    "TestScenario",
    "TestName",
    "ProfileName",
    "Users",
    "SpawnRate",
    "RunTimeSeconds",
    "EngineInstances",
    "EngineId",
    "ALTTestRunId",
    "Labels",
    "Timestamp",
}


def test_all_tables_include_common_envelope() -> None:
    for table in ALL_TABLES:
        names = {name for name, _ in TABLE_SCHEMAS[table]}
        missing = _COMMON - names
        assert not missing, f"{table} missing {missing}"


def test_columns_for_matches_table_schemas() -> None:
    for table in ALL_TABLES:
        assert columns_for(table) == TABLE_SCHEMAS[table]


def test_metrics_table_has_status_and_percentile_columns() -> None:
    names = {name for name, _ in columns_for(METRICS_TABLE)}
    for col in (
        "Service",
        "Count2xx",
        "Count3xx",
        "Count4xx",
        "Count5xx",
        "CountOther",
        "StatusCodes",
        "ResponseTime50th",
        "ResponseTime95th",
        "ResponseTime99th",
        "Throughput",
    ):
        assert col in names, f"{col} missing from {METRICS_TABLE}"


def test_summary_table_has_duration_columns() -> None:
    names = {name for name, _ in columns_for(SUMMARY_TABLE)}
    for col in ("TestStartTime", "TestEndTime", "TestDurationSeconds", "TotalRequests"):
        assert col in names


def test_exceptions_table_has_error_columns() -> None:
    names = {name for name, _ in columns_for(EXCEPTIONS_TABLE)}
    for col in ("Error", "ErrorMessage", "Traceback", "Occurrences"):
        assert col in names


def test_timeseries_table_has_bucket_columns() -> None:
    names = {name for name, _ in columns_for(TIMESERIES_TABLE)}
    for col in ("BucketStart", "BucketDurationSeconds", "RequestsPerSec"):
        assert col in names


def test_provisioning_script_emits_three_commands_per_table() -> None:
    commands = build_provisioning_script()
    assert len(commands) == 3 * len(ALL_TABLES)
    for table in ALL_TABLES:
        assert any(cmd.startswith(f".create-merge table {table} (") for cmd in commands), (
            f"missing create-merge for {table}"
        )
        assert any(cmd.startswith(f".alter-merge table {table} (") for cmd in commands), (
            f"missing alter-merge for {table}"
        )
        assert any(f'"{table}_mapping"' in cmd and ".create-or-alter" in cmd for cmd in commands), (
            f"missing mapping for {table}"
        )


def test_provisioning_script_has_no_duplicate_columns_per_table() -> None:
    for table, cols in TABLE_SCHEMAS.items():
        names = [name for name, _ in cols]
        assert len(names) == len(set(names)), f"{table} has duplicate columns"
