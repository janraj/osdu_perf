"""Kusto telemetry plugin — ingests test metrics into Azure Data Explorer."""

import io
import os
import csv
import time
import logging
from urllib.parse import urlparse

from ..plugin_base import TelemetryPlugin
from ..report import TestReport

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema definitions — SINGLE SOURCE OF TRUTH
# Each schema is a list of (column_name, kusto_type) tuples.
# Column lists, KQL .create-merge, and CSV headers are ALL derived from these.
# To add/remove/rename a column, edit ONLY the schema tuple list below.
# ---------------------------------------------------------------------------

METRICS_SCHEMA = [
    # --- osdu_perf metadata ---
    ("TestEnv", "string"), ("ADME", "string"), ("Partition", "string"),
    ("SKU", "string"), ("Version", "string"), ("TestRunId", "string"),
    ("TestScenario", "string"), ("Timestamp", "datetime"), ("Service", "string"),
    # --- Locust StatsEntry ---
    ("Name", "string"), ("Method", "string"),
    ("Requests", "long"), ("Failures", "long"), ("NumNoneRequests", "long"),
    ("TotalResponseTime", "long"),
    ("MinResponseTime", "real"), ("MaxResponseTime", "real"),
    ("TotalContentLength", "long"),
    ("StartTime", "datetime"), ("LastRequestTimestamp", "datetime"),
    ("MedianResponseTime", "real"), ("AverageResponseTime", "real"),
    ("CurrentRPS", "real"), ("CurrentFailPerSec", "real"),
    ("TotalRPS", "real"), ("TotalFailPerSec", "real"),
    ("FailRatio", "real"), ("AvgContentLength", "real"),
    # --- Percentiles ---
    ("ResponseTime50th", "real"), ("ResponseTime60th", "real"),
    ("ResponseTime70th", "real"), ("ResponseTime80th", "real"),
    ("ResponseTime90th", "real"), ("ResponseTime95th", "real"),
    ("ResponseTime98th", "real"), ("ResponseTime99th", "real"),
    ("ResponseTime999th", "real"), ("ResponseTime9999th", "real"),
    ("ResponseTime100th", "real"),
    # --- osdu_perf computed ---
    ("AverageRPS", "real"), ("RequestsPerSec", "real"),
    ("FailuresPerSec", "real"), ("Throughput", "real"),
]

EXCEPTIONS_SCHEMA = [
    ("TestEnv", "string"), ("TestRunId", "string"), ("ADME", "string"),
    ("SKU", "string"), ("Version", "string"), ("Partition", "string"),
    ("TestScenario", "string"), ("Timestamp", "datetime"), ("Service", "string"),
    ("Method", "string"), ("Name", "string"), ("Error", "string"),
    ("Occurrences", "long"), ("Traceback", "string"), ("ErrorMessage", "string"),
]

SUMMARY_SCHEMA = [
    ("TestEnv", "string"), ("TestRunId", "string"), ("ADME", "string"),
    ("Partition", "string"), ("SKU", "string"), ("Version", "string"),
    ("TestScenario", "string"), ("Timestamp", "datetime"),
    ("TotalRequests", "long"), ("TotalFailures", "long"),
    ("NumNoneRequests", "long"), ("TotalResponseTime", "long"),
    ("MinResponseTime", "real"), ("MaxResponseTime", "real"),
    ("TotalContentLength", "long"),
    ("StartTime", "datetime"), ("EndTime", "datetime"),
    ("MedianResponseTime", "real"), ("AvgResponseTime", "real"),
    ("CurrentRPS", "real"), ("CurrentFailPerSec", "real"),
    ("TotalRPS", "real"), ("TotalFailPerSec", "real"),
    ("FailRatio", "real"), ("AvgContentLength", "real"),
    ("ResponseTime50th", "real"), ("ResponseTime60th", "real"),
    ("ResponseTime70th", "real"), ("ResponseTime80th", "real"),
    ("ResponseTime90th", "real"), ("ResponseTime95th", "real"),
    ("ResponseTime98th", "real"), ("ResponseTime99th", "real"),
    ("ResponseTime999th", "real"), ("ResponseTime9999th", "real"),
    ("ResponseTime100th", "real"),
    ("TestDurationSeconds", "real"), ("AverageRPS", "real"),
    ("RequestsPerSec", "real"), ("FailuresPerSec", "real"),
    ("Throughput", "real"),
]

# ---------------------------------------------------------------------------
# Table registry — table names and their schemas in one place
# ---------------------------------------------------------------------------

TABLE_REGISTRY = {
    "LocustMetricsV3":      METRICS_SCHEMA,
    "LocustExceptionsV3":   EXCEPTIONS_SCHEMA,
    "LocustTestSummaryV3":  SUMMARY_SCHEMA,
}

# Table name constants for use in publish()
TABLE_METRICS    = "LocustMetricsV3"
TABLE_EXCEPTIONS = "LocustExceptionsV3"
TABLE_SUMMARY    = "LocustTestSummaryV3"


def _columns_from_schema(schema):
    """Extract ordered column name list from a schema definition."""
    return [col for col, _ in schema]


def _build_create_merge_kql(table_name, schema):
    """Generate .create-merge table KQL from a schema definition."""
    col_defs = ", ".join(f"{col}: {ktype}" for col, ktype in schema)
    return f".create-merge table {table_name} ({col_defs})"


def _create_csv_string(data_list, columns):
    """Serialize a list of row dicts to a CSV string with the given column order."""
    if not data_list:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(data_list)
    return output.getvalue()


class KustoPlugin(TelemetryPlugin):
    """Publishes test metrics to Azure Data Explorer (Kusto)."""

    def name(self) -> str:
        return "kusto"

    def is_enabled(self, config: dict) -> bool:
        kusto_cfg = config.get("kusto", {})
        if not kusto_cfg:
            return False
        # Explicit toggle takes precedence
        enabled_flag = kusto_cfg.get("enabled")
        if enabled_flag is not None:
            return bool(enabled_flag)
        # Fallback: enabled if cluster AND database are explicitly configured
        cluster = (kusto_cfg.get("cluster") or "").strip()
        database = (kusto_cfg.get("database") or "").strip()
        return bool(cluster and database)

    def publish(self, report: TestReport) -> None:
        # Lazy imports — only needed when Kusto is actually used
        from azure.kusto.ingest import QueuedIngestClient, IngestionProperties
        from azure.kusto.data import KustoConnectionStringBuilder, DataFormat

        total_start = time.time()
        kusto_cfg = self._resolve_config()
        cluster = kusto_cfg["cluster"]
        database = kusto_cfg["database"]

        # Auto-derive ingest_uri from cluster hostname
        hostname = urlparse(cluster).hostname
        ingest_uri = f"https://ingest-{hostname}"

        # Auth — same credentials for both management and ingestion
        is_azure = os.getenv("AZURE_LOAD_TEST", "").lower() == "true"
        auth_method = "managed_identity" if is_azure else "az_cli"
        logger.info(f"Kusto plugin enabled — cluster: {hostname}, database: {database}")
        logger.info(f"Using auth: {auth_method}")

        if is_azure:
            kcsb_mgmt = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(cluster)
            kcsb_ingest = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(ingest_uri)
        else:
            kcsb_mgmt = KustoConnectionStringBuilder.with_az_cli_authentication(cluster)
            kcsb_ingest = KustoConnectionStringBuilder.with_az_cli_authentication(ingest_uri)

        # --- Ensure database & tables exist (idempotent) ---
        self._ensure_database_and_tables(kcsb_mgmt, database)

        # --- Ingest data ---
        ingest_client = QueuedIngestClient(kcsb_ingest)
        meta = report.metadata
        ts_iso = meta.timestamp.isoformat()
        logger.info(f"Ingesting metrics for test_run_id={meta.test_run_id}")

        # --- Metrics ---
        self._ingest_metrics(ingest_client, report, meta, ts_iso, database, DataFormat.CSV)

        # --- Exceptions ---
        self._ingest_exceptions(ingest_client, report, meta, ts_iso, database, DataFormat.CSV)

        # --- Summary ---
        self._ingest_summary(ingest_client, report, meta, ts_iso, database, DataFormat.CSV)

        logger.info(f"Total ingestion completed in {time.time() - total_start:.1f}s")

    # ------------------------------------------------------------------
    # Row builders — one per table
    # ------------------------------------------------------------------

    @staticmethod
    def _build_metrics_row(meta, ts_iso, ep):
        return {
            "TestEnv": meta.test_run_environment,
            "ADME": meta.adme_name, "Partition": meta.partition,
            "SKU": meta.performance_tier, "Version": meta.version,
            "TestRunId": meta.test_run_id, "TestScenario": meta.test_scenario,
            "Timestamp": ts_iso,
            "Service": ep.service, "Name": ep.name, "Method": ep.method,
            "Requests": ep.requests, "Failures": ep.failures,
            "NumNoneRequests": ep.num_none_requests,
            "TotalResponseTime": ep.total_response_time,
            "MinResponseTime": ep.min_response_time,
            "MaxResponseTime": ep.max_response_time,
            "TotalContentLength": ep.total_content_length,
            "StartTime": ep.start_time,
            "LastRequestTimestamp": ep.last_request_timestamp,
            "MedianResponseTime": ep.median_response_time,
            "AverageResponseTime": ep.average_response_time,
            "CurrentRPS": ep.current_rps,
            "CurrentFailPerSec": ep.current_fail_per_sec,
            "TotalRPS": ep.total_rps,
            "TotalFailPerSec": ep.total_fail_per_sec,
            "FailRatio": ep.fail_ratio,
            "AvgContentLength": ep.avg_content_length,
            "ResponseTime50th": ep.percentiles.get("50th", 0),
            "ResponseTime60th": ep.percentiles.get("60th", 0),
            "ResponseTime70th": ep.percentiles.get("70th", 0),
            "ResponseTime80th": ep.percentiles.get("80th", 0),
            "ResponseTime90th": ep.percentiles.get("90th", 0),
            "ResponseTime95th": ep.percentiles.get("95th", 0),
            "ResponseTime98th": ep.percentiles.get("98th", 0),
            "ResponseTime99th": ep.percentiles.get("99th", 0),
            "ResponseTime999th": ep.percentiles.get("999th", 0),
            "ResponseTime9999th": ep.percentiles.get("9999th", 0),
            "ResponseTime100th": ep.percentiles.get("100th", 0),
            "AverageRPS": ep.average_rps,
            "RequestsPerSec": ep.requests_per_sec,
            "FailuresPerSec": ep.failures_per_sec,
            "Throughput": ep.throughput,
        }

    @staticmethod
    def _build_exception_row(meta, ts_iso, ex):
        return {
            "TestEnv": meta.test_run_environment,
            "TestRunId": meta.test_run_id, "ADME": meta.adme_name,
            "SKU": meta.performance_tier, "Version": meta.version,
            "Partition": meta.partition,
            "TestScenario": meta.test_scenario, "Timestamp": ts_iso,
            "Service": ex.service,
            "Method": ex.method, "Name": ex.name,
            "Error": ex.error, "Occurrences": ex.occurrences,
            "Traceback": ex.traceback, "ErrorMessage": ex.error_message,
        }

    @staticmethod
    def _build_summary_row(meta, ts_iso, s):
        return {
            "TestEnv": meta.test_run_environment,
            "TestRunId": meta.test_run_id, "ADME": meta.adme_name,
            "Partition": meta.partition, "SKU": meta.performance_tier,
            "Version": meta.version, "TestScenario": meta.test_scenario,
            "Timestamp": ts_iso,
            "TotalRequests": s.total_requests, "TotalFailures": s.total_failures,
            "NumNoneRequests": s.num_none_requests,
            "TotalResponseTime": s.total_response_time,
            "MinResponseTime": s.min_response_time,
            "MaxResponseTime": s.max_response_time,
            "TotalContentLength": s.total_content_length,
            "StartTime": s.start_time, "EndTime": s.end_time,
            "MedianResponseTime": s.median_response_time,
            "AvgResponseTime": s.avg_response_time,
            "CurrentRPS": s.current_rps,
            "CurrentFailPerSec": s.current_fail_per_sec,
            "TotalRPS": s.total_rps,
            "TotalFailPerSec": s.total_fail_per_sec,
            "FailRatio": s.fail_ratio,
            "AvgContentLength": s.avg_content_length,
            "ResponseTime50th": s.percentiles.get("50th", 0),
            "ResponseTime60th": s.percentiles.get("60th", 0),
            "ResponseTime70th": s.percentiles.get("70th", 0),
            "ResponseTime80th": s.percentiles.get("80th", 0),
            "ResponseTime90th": s.percentiles.get("90th", 0),
            "ResponseTime95th": s.percentiles.get("95th", 0),
            "ResponseTime98th": s.percentiles.get("98th", 0),
            "ResponseTime99th": s.percentiles.get("99th", 0),
            "ResponseTime999th": s.percentiles.get("999th", 0),
            "ResponseTime9999th": s.percentiles.get("9999th", 0),
            "ResponseTime100th": s.percentiles.get("100th", 0),
            "TestDurationSeconds": s.test_duration_seconds,
            "AverageRPS": s.average_rps,
            "RequestsPerSec": s.requests_per_sec,
            "FailuresPerSec": s.failures_per_sec,
            "Throughput": s.throughput,
        }

    # ------------------------------------------------------------------
    # Ingest helpers
    # ------------------------------------------------------------------

    def _ingest_metrics(self, ingest_client, report, meta, ts_iso, database, data_format):
        from azure.kusto.ingest import IngestionProperties
        rows = [self._build_metrics_row(meta, ts_iso, ep) for ep in report.endpoint_stats]
        if rows:
            t0 = time.time()
            columns = _columns_from_schema(METRICS_SCHEMA)
            csv_data = _create_csv_string(rows, columns)
            ingest_client.ingest_from_stream(
                io.StringIO(csv_data),
                IngestionProperties(database=database, table=TABLE_METRICS, data_format=data_format),
            )
            logger.info(f"{TABLE_METRICS}: {len(rows)} endpoint rows ingested ({time.time() - t0:.1f}s)")

    def _ingest_exceptions(self, ingest_client, report, meta, ts_iso, database, data_format):
        from azure.kusto.ingest import IngestionProperties
        rows = [self._build_exception_row(meta, ts_iso, ex) for ex in report.exceptions]
        if rows:
            t0 = time.time()
            columns = _columns_from_schema(EXCEPTIONS_SCHEMA)
            csv_data = _create_csv_string(rows, columns)
            ingest_client.ingest_from_stream(
                io.StringIO(csv_data),
                IngestionProperties(database=database, table=TABLE_EXCEPTIONS, data_format=data_format),
            )
            logger.info(f"{TABLE_EXCEPTIONS}: {len(rows)} error rows ingested ({time.time() - t0:.1f}s)")

    def _ingest_summary(self, ingest_client, report, meta, ts_iso, database, data_format):
        from azure.kusto.ingest import IngestionProperties
        if report.summary:
            t0 = time.time()
            rows = [self._build_summary_row(meta, ts_iso, report.summary)]
            columns = _columns_from_schema(SUMMARY_SCHEMA)
            csv_data = _create_csv_string(rows, columns)
            ingest_client.ingest_from_stream(
                io.StringIO(csv_data),
                IngestionProperties(database=database, table=TABLE_SUMMARY, data_format=data_format),
            )
            logger.info(f"{TABLE_SUMMARY}: 1 summary row ingested ({time.time() - t0:.1f}s)")

    # ------------------------------------------------------------------
    # Auto-create database & tables
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_database_and_tables(kcsb, database: str) -> None:
        """Ensure Kusto database and tables exist (idempotent).

        Uses .create-merge table which is safe to run every time:
        - Creates the table if it doesn't exist
        - Adds new columns if the table already exists
        - Never drops existing columns or data
        """
        from azure.kusto.data import KustoClient

        mgmt_client = KustoClient(kcsb)

        # 1. Try to create database (requires cluster-level admin)
        try:
            mgmt_client.execute_mgmt(
                "",  # empty database for cluster-level command
                f".create database ['{database}'] ifnotexists",
            )
            logger.info(f"Database ensured: {database}")
        except Exception:
            logger.debug(f"Could not create database '{database}' (likely already exists or insufficient permissions)")

        # 2. Create-merge tables — KQL generated from schema definitions
        logger.info("Ensuring tables exist (create-merge)...")
        table_names = []
        for table_name, schema in TABLE_REGISTRY.items():
            kql = _build_create_merge_kql(table_name, schema)
            try:
                mgmt_client.execute_mgmt(database, kql)
                table_names.append(table_name)
            except Exception:
                logger.warning(
                    f"Could not create-merge table '{table_name}' — it may already exist or permissions are insufficient",
                    exc_info=True,
                )

        logger.info(f"Tables verified: {', '.join(table_names) if table_names else 'none (see warnings above)'}")

    # ------------------------------------------------------------------
    # Config resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_config() -> dict:
        """Resolve Kusto config from InputHandler.

        Only 'cluster' is required. 'database' defaults to 'adme-performance-db'.
        'ingest_uri' is auto-derived from cluster hostname.
        """
        from ...locust_integration.user import PerformanceUser
        ih = PerformanceUser._input_handler_instance
        if ih:
            cfg = ih.get_kusto_config()
        else:
            cfg = {
                "cluster": "https://adme-performance.eastus.kusto.windows.net",
                "database": "adme-performance-db",
            }

        # Ensure database has a default
        if not cfg.get("database"):
            cfg["database"] = "adme-performance-db"

        # Auto-derive ingest_uri from cluster (no longer needed in config)
        cluster = cfg.get("cluster", "")
        hostname = urlparse(cluster).hostname or ""
        cfg["ingest_uri"] = f"https://ingest-{hostname}"

        return cfg
