# Changes — `osdu_perf` v2 cleanup

Summary of the breaking changes introduced on this branch (`sabz/enhancements`)
as part of the v2 major-version reset. All legacy / backward-compat paths have
been removed in favour of a single clean configuration shape.

## 1. New `system_config.yaml` shape

```yaml
osdu_environment:
  host: "https://<your-osdu>"
  partition: "<partition>"
  app_id: "<aad-app-id>"

# Free-form labels. Every key/value lands in the Kusto Metadata dynamic
# column. `performance_tier` also selects the matching profile from
# test_config.yaml:performance_tier_profiles.
test_metadata:
  performance_tier: "flex"
  version: "25.8.112"
  # region: "eastus"         # optional free-form tags
  # build: "pr-1234"

azure_infra:
  subscription_id: "<sub>"
  resource_group: "<rg>"
  location: "<region>"

  # Safety switch — default false. When false, the tool will NEVER create
  # the resource group or the Azure Load Test resource and will fail fast
  # with a clear error if they don't exist. Flip to true to opt in.
  allow_resource_creation: false

  azure_load_test:
    # Must already exist unless allow_resource_creation is true.
    # Overridable via --loadtest-name.
    name: "<existing-alt-resource>"

  kusto:
    # Provide EITHER cluster_uri OR ingest_uri — the other is derived by
    # adding/removing the `ingest-` hostname prefix. Specifying both is
    # allowed only if they're consistent.
    cluster_uri: "https://<name>.<region>.kusto.windows.net"
    database: "<db>"
```

### Per-scenario overrides (unchanged, documented for clarity)

`test_config.yaml` can override any `test_metadata` key per scenario:

```yaml
scenarios:
  search_query_random_id:
    metadata:
      build: "pr-1234"
```

## 2. Safety: no silent Azure resource creation

`azure_infra.allow_resource_creation` (default **`false`**) gates creation
of both the resource group and the Azure Load Test resource. When the flag
is off and a resource is missing, the run fails with an explicit
`RuntimeError` explaining what to fix, instead of quietly provisioning
infrastructure.

## 3. Kusto URI deduplication

Only one of `cluster_uri` or `ingest_uri` is needed. The other is derived
automatically by adding/removing the `ingest-` hostname prefix. The
`QueuedIngestClient` now correctly uses the ingest URI, not the query URI.

## 4. Kusto schema (V2 tables)

Telemetry is written to V2 tables with a single `Metadata: dynamic`
column that carries everything from `test_metadata`:

- `LocustMetricsV2`
- `LocustExceptionsV2`
- `LocustTestSummaryV2`

Ingestion uses the `MULTIJSON` format.

## 5. CLI changes

Removed (no longer flags; use `test_metadata` in config instead):

- `--sku`
- `--version`

`--loadtest-name` no longer has a hidden default of `osdu-perf-dev`. The
ALT resource name must come from `azure_infra.azure_load_test.name` or
the `--loadtest-name` override.

## 6. Removed legacy config keys

The following keys are **no longer read** anywhere:

- `test_environment.*`               → use `azure_infra.*`
- `metrics_collector.*`              → use `azure_infra.kusto.*`
- `osdu_environment.performance_tier` / `osdu_environment.version`
                                     → use `test_metadata.*`
- `azure_infra.kusto.cluster`        → use `kusto.cluster_uri`
- `sku_profiles` / `instance_profiles` alternates for
  `performance_tier_profiles`

## 7. Removed internal APIs

- `InputHandler.get_osdu_sku()`
- `InputHandler.get_osdu_version()`
- `InputHandler.get_metrics_collector_config()` (dead code)
- `AzureLoadTestConfig.sku`, `AzureLoadTestConfig.version` dataclass fields
- `AzureLoadTestRunner.__init__(sku=..., version=...)` params
- `AzureLoadTestRunner.create_test(test_metadata=...)` param
- `AzureLoadTestRunner.create_tests_and_upload_test_files(test_metadata=...)`
  param
- `SKU` / `VERSION` / `TEST_METADATA` environment variables injected into
  the ALT engine (tests now read metadata from `system_config.yaml` that
  is uploaded alongside the Locust files)

## 8. Files touched

```
osdu_perf/cli/arg_parser.py
osdu_perf/cli/commands/run_azure_command.py
osdu_perf/locust_integration/user_base.py
osdu_perf/operations/auth.py
osdu_perf/operations/azure_test_operation/azure_test_runner.py
osdu_perf/operations/azure_test_operation/config.py
osdu_perf/operations/azure_test_operation/resource_manager.py
osdu_perf/operations/init_operation/init_runner.py
osdu_perf/operations/input_handler.py
```

## 9. Migration checklist (for existing users)

1. In `system_config.yaml`:
   - Move `osdu_environment.performance_tier` / `.version` into a new
     top-level `test_metadata:` block.
   - Rename `test_environment:` → `azure_infra:` and/or merge
     `metrics_collector:` into `azure_infra.kusto:`.
   - Add `azure_infra.azure_load_test.name: <existing-alt-resource>`.
   - Replace `kusto.cluster:` with `kusto.cluster_uri:` (or use
     `ingest_uri`).
   - Decide whether to set `azure_infra.allow_resource_creation: true`
     (opt-in) or pre-create RG + ALT resource.
2. Drop `--sku` / `--version` from any CLI wrappers or CI pipelines.
3. If you relied on `SKU` / `VERSION` / `TEST_METADATA` env vars inside
   custom tests, read from `input_handler.get_test_metadata()` instead.

## 10. Test status

```
pytest tests/unit → 138 passed, 2 warnings in 7.74s
```
