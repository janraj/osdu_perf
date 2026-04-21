# Telemetry Plugin Architecture — Tech Design

**Author:** osdu_perf team  
**Status:** Implemented  
**Version:** V3

---

## 1. Overview

The `osdu_perf` telemetry system is a SOLID plugin-based architecture that collects Locust performance metrics at the end of each test run and pushes them to one or more configurable backends. Currently the only backend is **Azure Data Explorer (Kusto)**, but the design allows adding new backends (CSV, App Insights, Prometheus, etc.) by adding a single plugin file.

### Key Capabilities

- Plugin-based extensibility — new backends require zero changes to existing code
- Schema-driven table definitions — single source of truth for columns, types, and KQL
- Auto-create Kusto database and tables (idempotent `.create-merge table`)
- Auto-derive `ingest_uri` from cluster URL — no extra config needed
- Environment-aware auth (Managed Identity in Azure Load Test, Az CLI locally)
- Per-table timing logs and structured observability
- All Locust stats fields mapped (42 metrics, 15 exception, 38 summary columns)

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────┐
│              Locust events.test_stop                     │
│                       │                                  │
│                       ▼                                  │
│           ┌─────────────────────┐                        │
│           │  TelemetryDispatcher │  (orchestrator)        │
│           │  - collects stats    │                        │
│           │  - builds TestReport │                        │
│           │  - fans out to       │                        │
│           │    enabled plugins   │                        │
│           └────────┬────────────┘                        │
│                    │                                     │
│          ┌─────────┼──────────┐                          │
│          ▼         ▼          ▼                          │
│  ┌──────────────┐ ┌────────┐ ┌───────────────┐          │
│  │ KustoPlugin  │ │  CSV   │ │ AppInsights   │  ...     │
│  │ (built-in)   │ │(future)│ │   (future)    │          │
│  └──────────────┘ └────────┘ └───────────────┘          │
│                                                          │
│  All plugins implement TelemetryPlugin ABC               │
└──────────────────────────────────────────────────────────┘
```

### SOLID Compliance

| Principle | How it's met |
|---|---|
| **S — Single Responsibility** | `TestReport` = data, `KustoPlugin` = Kusto backend, `Dispatcher` = orchestration |
| **O — Open/Closed** | New backend = new plugin file + one line in `discover_plugins()`, zero changes to dispatcher |
| **L — Liskov Substitution** | Any `TelemetryPlugin` subclass is interchangeable in the dispatcher loop |
| **I — Interface Segregation** | `TelemetryPlugin` has exactly 3 methods — lean interface |
| **D — Dependency Inversion** | Dispatcher depends on `TelemetryPlugin` ABC, not on `azure-kusto-*` SDK |

---

## 3. File Structure

```
osdu_perf/
├── telemetry/
│   ├── __init__.py           # exports TelemetryDispatcher, discover_plugins, TestReport
│   ├── plugin_base.py        # TelemetryPlugin ABC (3 abstract methods)
│   ├── dispatcher.py         # TelemetryDispatcher + report builder
│   ├── report.py             # TestReport, TestMetadata, EndpointStat, ExceptionRecord, TestSummary
│   └── plugins/
│       ├── __init__.py
│       └── kusto_plugin.py   # KustoPlugin — schema-driven, auto-create tables, ingest
```

---

## 4. Core Interfaces

### 4.1 `TelemetryPlugin` — Abstract Base Class (`plugin_base.py`)

```python
class TelemetryPlugin(ABC):
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def is_enabled(self, config: dict) -> bool: ...

    @abstractmethod
    def publish(self, report: TestReport) -> None: ...
```

### 4.2 `TestReport` — Data Transfer Object (`report.py`)

A plain dataclass holding all collected metrics. Built once by the dispatcher, passed to every plugin.

```
TestReport
├── metadata: TestMetadata
│   ├── test_run_id: str
│   ├── test_scenario: str
│   ├── adme_name: str
│   ├── partition: str
│   ├── performance_tier: str
│   ├── version: str
│   ├── test_run_environment: str       # "Local" | "Azure Load Test"
│   ├── timestamp: datetime
│   ├── test_duration_seconds: float
│   └── max_rps: float
│
├── endpoint_stats: list[EndpointStat]  # per-endpoint metrics (42 columns)
├── exceptions: list[ExceptionRecord]   # per-error records (15 columns)
└── summary: TestSummary                # single aggregate record (38 columns)
```

### 4.3 `TelemetryDispatcher` — Orchestrator (`dispatcher.py`)

```python
class TelemetryDispatcher:
    def __init__(self, plugins: list[TelemetryPlugin], config: dict):
        self._plugins = [p for p in plugins if p.is_enabled(config)]

    def dispatch(self, environment, input_handler) -> None:
        report = self._build_report(environment, input_handler)
        for plugin in self._plugins:
            try:
                plugin.publish(report)
            except Exception:
                logger.error(f"Plugin '{plugin.name()}' failed", exc_info=True)
```

### 4.4 Plugin Discovery (`__init__.py`)

```python
def discover_plugins() -> list[TelemetryPlugin]:
    from .plugins.kusto_plugin import KustoPlugin
    return [KustoPlugin()]
```

Future plugins: add one import + one list entry. Zero changes to dispatcher.

### 4.5 Integration Point — `on_test_stop`

```python
@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    input_handler = PerformanceUser._input_handler_instance
    if not input_handler:
        return
    config = input_handler.get_metrics_collector_config()
    dispatcher = TelemetryDispatcher(plugins=discover_plugins(), config=config)
    dispatcher.dispatch(environment, input_handler)
```

---

## 5. KustoPlugin — Design

### 5.1 Schema-Driven Architecture (Single Source of Truth)

All table schemas are defined as Python tuples of `(column_name, kusto_type)` in `kusto_plugin.py`. Everything else is derived:

```python
# Schema definition — the ONLY place columns are defined
METRICS_SCHEMA = [
    ("TestEnv", "string"), ("ADME", "string"), ...
    ("Requests", "long"), ("Failures", "long"), ...
]

# Table registry — maps table names to schemas
TABLE_REGISTRY = {
    "LocustMetricsV3":      METRICS_SCHEMA,
    "LocustExceptionsV3":   EXCEPTIONS_SCHEMA,
    "LocustTestSummaryV3":  SUMMARY_SCHEMA,
}

# Table name constants
TABLE_METRICS    = "LocustMetricsV3"
TABLE_EXCEPTIONS = "LocustExceptionsV3"
TABLE_SUMMARY    = "LocustTestSummaryV3"
```

**Derived from schema (not hardcoded):**

| Artifact | Function |
|----------|----------|
| CSV column headers | `_columns_from_schema(schema)` → `["TestEnv", "ADME", ...]` |
| `.create-merge table` KQL | `_build_create_merge_kql(table_name, schema)` → KQL string |

To add/remove/rename a column: edit **only** the `*_SCHEMA` tuple list. The KQL, CSV headers, and column ordering all follow automatically.

### 5.2 Configuration

User only needs to provide `cluster`. Everything else is derived or defaulted:

```yaml
metrics_collector:
  kusto:
    cluster: "https://adme-performance.eastus.kusto.windows.net"
    database: "adme-performance-db"    # optional — defaults to "adme-performance-db"
```

**Derivation rules:**

| Field | Rule |
|-------|------|
| `cluster` | **Required** — the only mandatory input |
| `database` | Optional — defaults to `"adme-performance-db"` |
| `ingest_uri` | **Auto-derived**: `https://ingest-{cluster_hostname}` |
| `auth_method` | **Auto-detected**: `managed_identity` when `AZURE_LOAD_TEST=true`, `az_cli` otherwise |
| `enabled` | Plugin is enabled when `cluster` and `database` are non-empty, or `enabled: true` is set explicitly |

### 5.3 `publish()` Flow

```
KustoPlugin.publish(report)
    │
    ├── 1. _resolve_config() — cluster, database, auto-derive ingest_uri
    │
    ├── 2. Auth — KustoConnectionStringBuilder (ManagedIdentity or AzCli)
    │       Creates separate kcsb for management (cluster) and ingestion (ingest_uri)
    │
    ├── 3. _ensure_database_and_tables(kcsb_mgmt, database)
    │   ├── .create database ['{db}'] ifnotexists
    │   │   (catches permission errors gracefully)
    │   └── for each table in TABLE_REGISTRY:
    │       └── _build_create_merge_kql(name, schema) → execute_mgmt()
    │
    ├── 4. _ingest_metrics()
    │   ├── _build_metrics_row() per endpoint → list of dicts
    │   ├── _columns_from_schema(METRICS_SCHEMA) → CSV column order
    │   ├── _create_csv_string() → CSV string
    │   └── QueuedIngestClient.ingest_from_stream() → LocustMetricsV3
    │
    ├── 5. _ingest_exceptions()
    │   ├── _build_exception_row() per error → list of dicts
    │   └── ingest_from_stream() → LocustExceptionsV3
    │
    └── 6. _ingest_summary()
        ├── _build_summary_row() → single dict
        └── ingest_from_stream() → LocustTestSummaryV3
```

### 5.4 Method Decomposition

| Method | Responsibility |
|--------|---------------|
| `publish()` | Top-level orchestrator — config, auth, ensure tables, ingest all 3 tables |
| `_resolve_config()` | Reads config from InputHandler, applies defaults, derives `ingest_uri` |
| `_ensure_database_and_tables()` | Creates database (if permissions allow) + create-merge all tables from `TABLE_REGISTRY` |
| `_build_metrics_row()` | Maps `EndpointStat` → dict for one metrics row |
| `_build_exception_row()` | Maps `ExceptionRecord` → dict for one exception row |
| `_build_summary_row()` | Maps `TestSummary` → dict for one summary row |
| `_ingest_metrics()` | Builds all metric rows, serializes to CSV, ingests to `LocustMetricsV3` |
| `_ingest_exceptions()` | Builds all exception rows, serializes to CSV, ingests to `LocustExceptionsV3` |
| `_ingest_summary()` | Builds summary row, serializes to CSV, ingests to `LocustTestSummaryV3` |

### 5.5 Module-Level Helpers

| Function | Purpose |
|----------|---------|
| `_columns_from_schema(schema)` | Extracts ordered column name list from schema tuples |
| `_build_create_merge_kql(table_name, schema)` | Generates `.create-merge table` KQL from schema tuples |
| `_create_csv_string(data_list, columns)` | Serializes list of row dicts to CSV string with given column order |

---

## 6. Kusto Table Schemas

All tables use `V3` suffix. Schemas are defined in `kusto_plugin.py` as `*_SCHEMA` tuples and KQL is auto-generated via `_build_create_merge_kql()`.

### 6.1 `LocustMetricsV3` — Per-Endpoint Stats (42 columns)

| Column | Kusto Type | Source |
|--------|-----------|--------|
| **osdu_perf metadata** | | |
| TestEnv | string | `"Local"` \| `"Azure Load Test"` |
| ADME | string | Parsed from `environment.host` |
| Partition | string | `InputHandler.partition` |
| SKU | string | Performance tier |
| Version | string | OSDU version |
| TestRunId | string | `TEST_RUN_ID` env var |
| TestScenario | string | From config/tags |
| Timestamp | datetime | UTC time of report generation |
| Service | string | Derived from URL path |
| **Locust StatsEntry attributes** | | |
| Name | string | `StatsEntry.name` |
| Method | string | `StatsEntry.method` |
| Requests | long | `StatsEntry.num_requests` |
| Failures | long | `StatsEntry.num_failures` |
| NumNoneRequests | long | `StatsEntry.num_none_requests` |
| TotalResponseTime | long | `StatsEntry.total_response_time` |
| MinResponseTime | real | `StatsEntry.min_response_time` |
| MaxResponseTime | real | `StatsEntry.max_response_time` |
| TotalContentLength | long | `StatsEntry.total_content_length` |
| StartTime | datetime | `StatsEntry.start_time` (epoch → datetime) |
| LastRequestTimestamp | datetime | `StatsEntry.last_request_timestamp` |
| **Locust StatsEntry computed** | | |
| MedianResponseTime | real | `StatsEntry.median_response_time` |
| AverageResponseTime | real | `StatsEntry.avg_response_time` |
| CurrentRPS | real | `StatsEntry.current_rps` (10s window) |
| CurrentFailPerSec | real | `StatsEntry.current_fail_per_sec` (10s window) |
| TotalRPS | real | `StatsEntry.total_rps` (lifetime) |
| TotalFailPerSec | real | `StatsEntry.total_fail_per_sec` (lifetime) |
| FailRatio | real | `StatsEntry.fail_ratio` |
| AvgContentLength | real | `StatsEntry.avg_content_length` |
| **Percentiles** | | |
| ResponseTime50th–100th | real | `StatsEntry.get_response_time_percentile()` (11 values: p50, p60, p70, p80, p90, p95, p98, p99, p999, p9999, p100) |
| **osdu_perf computed** | | |
| AverageRPS | real | `num_requests / duration` |
| RequestsPerSec | real | From `num_reqs_per_sec` dict |
| FailuresPerSec | real | From `num_fail_per_sec` dict |
| Throughput | real | `total_content_length / duration` (bytes/s) |

### 6.2 `LocustExceptionsV3` — Error Tracking (15 columns)

| Column | Kusto Type | Source |
|--------|-----------|--------|
| TestEnv | string | Metadata |
| TestRunId | string | Metadata |
| ADME | string | Metadata |
| SKU | string | Metadata |
| Version | string | Metadata |
| Partition | string | Metadata |
| TestScenario | string | Metadata |
| Timestamp | datetime | Metadata |
| Service | string | Derived from URL path |
| Method | string | `StatsError.method` |
| Name | string | `StatsError.name` |
| Error | string | `StatsError.parse_error(error)` |
| Occurrences | long | `StatsError.occurrences` |
| Traceback | string | `StatsError` traceback |
| ErrorMessage | string | `StatsError` error message |

### 6.3 `LocustTestSummaryV3` — Aggregate Summary (38 columns)

| Column | Kusto Type | Source |
|--------|-----------|--------|
| TestEnv | string | Metadata |
| TestRunId | string | Metadata |
| ADME | string | Metadata |
| Partition | string | Metadata |
| SKU | string | Metadata |
| Version | string | Metadata |
| TestScenario | string | Metadata |
| Timestamp | datetime | Metadata |
| TotalRequests | long | `stats.total.num_requests` |
| TotalFailures | long | `stats.total.num_failures` |
| NumNoneRequests | long | `stats.total.num_none_requests` |
| TotalResponseTime | long | `stats.total.total_response_time` |
| MinResponseTime | real | `stats.total.min_response_time` |
| MaxResponseTime | real | `stats.total.max_response_time` |
| TotalContentLength | long | `stats.total.total_content_length` |
| StartTime | datetime | `stats.total.start_time` |
| EndTime | datetime | Current timestamp |
| MedianResponseTime | real | `stats.total.median_response_time` |
| AvgResponseTime | real | `stats.total.avg_response_time` |
| CurrentRPS | real | `stats.total.current_rps` |
| CurrentFailPerSec | real | `stats.total.current_fail_per_sec` |
| TotalRPS | real | `stats.total.total_rps` |
| TotalFailPerSec | real | `stats.total.total_fail_per_sec` |
| FailRatio | real | `stats.total.fail_ratio` |
| AvgContentLength | real | `stats.total.avg_content_length` |
| ResponseTime50th–100th | real | 11 percentile columns (same as metrics) |
| TestDurationSeconds | real | `end_time - start_time` |
| AverageRPS | real | `total_requests / duration` |
| RequestsPerSec | real | From `num_reqs_per_sec` dict |
| FailuresPerSec | real | From `num_fail_per_sec` dict |
| Throughput | real | `total_content_length / duration` |

---

## 7. Authentication

| Environment | Auth Method | Detection |
|-------------|-------------|-----------|
| Azure Load Test | `KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication()` | `AZURE_LOAD_TEST=true` env var |
| Local dev | `KustoConnectionStringBuilder.with_az_cli_authentication()` | Default fallback |

Two separate connection string builders are created:
- **`kcsb_mgmt`** → points to cluster URL, used for DDL commands (`KustoClient`)
- **`kcsb_ingest`** → points to `ingest_uri`, used for data ingestion (`QueuedIngestClient`)

---

## 8. Auto-Create Database & Tables

The `_ensure_database_and_tables()` method runs on every `publish()` call:

1. **Database**: `.create database ['{db}'] ifnotexists` — requires cluster-level admin. If permission denied, logs at `DEBUG` and continues (database assumed to exist).

2. **Tables**: Iterates `TABLE_REGISTRY` and runs `_build_create_merge_kql(name, schema)` for each table. `.create-merge table` is idempotent:
   - Creates the table if it doesn't exist
   - Adds new columns if the table already exists
   - Never drops existing columns or data
   - **Cannot** change an existing column's type (e.g., `int` → `long`)

---

## 9. Error Handling

| Scenario | Behavior |
|----------|----------|
| Database create fails (permission denied) | Log `DEBUG`, continue — database assumed to exist |
| Table create-merge fails | Log `WARNING` with traceback, continue |
| Ingestion fails | Log `ERROR` with traceback, do NOT re-raise |
| Plugin raises in `publish()` | Dispatcher catches, logs error, continues to next plugin |
| No plugins enabled | Dispatcher logs info and returns immediately |
| Missing config / empty cluster | `is_enabled()` returns `False`, plugin skipped |

**Critical rule:** Telemetry failures never affect test run status.

---

## 10. Logging & Observability

### KustoPlugin logs

```
INFO  Kusto plugin enabled — cluster: adme-performance.eastus.kusto.windows.net, database: adme-performance-db
INFO  Using auth: managed_identity
INFO  Ensuring tables exist (create-merge)...
INFO  Tables verified: LocustMetricsV3, LocustExceptionsV3, LocustTestSummaryV3
INFO  Ingesting metrics for test_run_id=record_size_1KB_Flex_25_9_17_20260420_155204
INFO  LocustMetricsV3: 12 endpoint rows ingested (0.8s)
INFO  LocustExceptionsV3: 3 error rows ingested (0.2s)
INFO  LocustTestSummaryV3: 1 summary row ingested (0.1s)
INFO  Total ingestion completed in 1.1s
```

### Dispatcher logs

```
INFO  Enabled plugins: ['kusto']
INFO  TestReport built: 12 endpoints, 3 errors, duration=1800.0s, total_requests=45230
INFO  Telemetry plugin 'kusto' completed successfully
INFO  All plugins completed successfully
```

On failure:
```
ERROR Telemetry plugin 'kusto' failed — metrics NOT sent
INFO  Test run completed (telemetry errors do not affect test status)
```

---

## 11. Configuration (`system_config.yaml`)

### Minimal (just cluster):

```yaml
metrics_collector:
  kusto:
    cluster: "https://adme-performance.eastus.kusto.windows.net"
```

### Full (with optional overrides):

```yaml
metrics_collector:
  kusto:
    cluster: "https://my-custom-cluster.westus2.kusto.windows.net"
    database: "my-custom-db"
```

### Disable telemetry:

```yaml
# Remove or comment out the metrics_collector section
# metrics_collector:
#   kusto:
#     cluster: "..."
```

---

## 12. Future Plugins (not in scope — showing extensibility)

| Plugin | Config key | Backend | Trigger |
|---|---|---|---|
| `CSVPlugin` | `metrics_collector.csv` | Local CSV files | When `output_dir` is set |
| `AppInsightsPlugin` | `metrics_collector.app_insights` | Azure Monitor | When `connection_string` is set |
| `PrometheusPlugin` | `metrics_collector.prometheus` | Prometheus push gateway | When `push_url` is set |
| `WebhookPlugin` | `metrics_collector.webhook` | HTTP POST | When `url` is set |

Each plugin: one file in `telemetry/plugins/`, one line in `discover_plugins()`. Zero changes to dispatcher or existing plugins.
