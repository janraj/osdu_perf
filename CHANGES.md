# Changelog

## 2.0.0 — Full rewrite

Complete refactor for open-source release quality. **Breaking**: no
backward compatibility with v1.x. v1 remains what is in production; v2 is
the new baseline going forward.

---

## User-facing changes

These are everything a test author or CI pipeline will notice.

### CLI

| v1                                            | v2                                                             |
| --------------------------------------------- | -------------------------------------------------------------- |
| `osdu_perf init search`                       | `osdu_perf init --sample=search_query`                         |
| `osdu_perf run local --partition opendes ...` | `osdu_perf run local --scenario search_query`                  |
| *(no equivalent)*                             | `osdu_perf run azure --scenario search_query`                  |
| *(no equivalent)*                             | `osdu_perf validate`                                           |
| *(no equivalent)*                             | `osdu_perf samples`                                            |
| *(no equivalent)*                             | `osdu_perf version`                                            |
| *(no equivalent)*                             | `osdu_perf <any-command> --verbose`                            |

* `init` now takes `--sample=<name>` (default `storage_crud`), not a
  positional service name. `--list-samples` and `--force` are available.
* `run` is split into `run local` and `run azure` subcommands.
* All long flags are kebab-case: `--load-test-name`, `--app-id`,
  `--bearer-token`, `--spawn-rate`, `--run-time`.
* `--scenario` is required for both run subcommands and must exist in
  `config/test_config.yaml`.
* `--profile` is optional on both `run local` and `run azure`; it
  overrides the scenario's `profile:` field.
* Error output is clean by default — pass `-v` / `--verbose` for the full
  traceback.

### Scaffolded project layout

`osdu_perf init --sample=<name>` now writes a complete project tree:

```
./
├── config/
│   ├── system_config.yaml
│   └── test_config.yaml
├── locustfile.py
├── perf_<sample>_test.py
├── requirements.txt
└── README.md
```

Bundled samples: `storage_crud`, `search_query`, `schema_browse`. Run
`osdu_perf samples` to list them.

### Configuration

Two typed YAML files with a clean split between platform and test:

* `config/system_config.yaml` — **platform only**, with two independent
  top-level sections:
  * `azure_load_test` — subscription, resource group, location,
    `allow_resource_creation`, and ALT resource `name`. Used only by
    `osdu_perf run azure`.
  * `kusto_export` — optional telemetry sink (`cluster_uri` or
    `ingest_uri`, plus `database`). Used by **both** `osdu_perf run
    local` and `osdu_perf run azure`.
* `config/test_config.yaml` — **everything about the test**:
  `osdu_environment` (host/partition/app_id), `test_metadata`,
  `test_settings` (defaults), `profiles`, and `scenarios`.

The previous flat `azure_infra:` block (which nested `azure_load_test`
and `kusto`) no longer exists — the two concerns are now siblings at
the top of `system_config.yaml`.

`test_metadata` is now pure passthrough — every key/value is copied
verbatim to each Kusto telemetry row and the framework never interprets
it.

Profile selection is explicit via the CLI or the scenario itself:

```
--profile <name>   >   scenarios.<name>.profile   >   profiles.default   >   no profile
```

Then `scenarios.<name>` overrides (`users`, `spawn_rate`, `run_time`, …)
always win over the selected profile.

The old section name `performance_tier_profiles:` was renamed to
`profiles:` to match the new model.

### Public Python API

Stable imports from `osdu_perf`:

```python
from osdu_perf import (
    __version__,
    AppConfig,
    load_config,
    BaseService,
    PerformanceUser,
    ServiceRegistry,
)
```

* `PerformanceUser` is still a Locust `HttpUser` subclass, with
  `get_host()`, `get_partition()`, `get_appid()`, `get_token()`,
  `get_headers()`, `get_request_headers(extra=None)`, and
  `new_correlation_id()` helpers.
* `BaseService` methods (`execute`, `prehook`, `posthook`,
  `provide_explicit_token`) are now `abstractmethod` — subclasses must
  implement all four.
* `ServiceRegistry` replaces `ServiceOrchestrator`. Discovery is explicit:
  `registry.discover(client, root=Path('.'))`.

### Errors

All library errors now inherit from `osdu_perf.errors.OsduPerfError`.
Catching this base class is enough for CLI wrappers:

* `ConfigError` — bad or missing YAML.
* `ScenarioNotFoundError` — scenario not in `test_config.yaml`.
* `AuthError` — token acquisition failed.
* `AzureResourceError` — ALT resource missing / Graph call failed.
* `ScaffoldError` — `init` collision, unknown sample.

### Telemetry (Kusto)

Table names are stable (`LocustMetricsV2`, `LocustExceptionsV2`,
`LocustTestSummaryV2`). Ingestion is skipped automatically when
`kusto_export` is not configured, and is invoked from Locust's
`test_stop` hook for **both** local and Azure Load Testing runs.

### Authentication

`TokenProvider` honours, in order:

1. `--bearer-token` CLI flag or `ADME_BEARER_TOKEN` env var.
2. Managed identity (when running inside Azure Load Testing — detected
   via `AZURE_LOAD_TEST` / `LOCUST_*` env vars).
3. `az account get-access-token --resource <app_id>` (preserves the
   `aud=<appId>` claim that OSDU expects).
4. `AzureCliCredential` fallback if `az` isn't on PATH.

Tokens are cached per `app_id` within a single process.

---

## Technical changes

### New package layout

```
osdu_perf/
├── _version.py       Single source of truth for __version__
├── errors.py         Typed exception hierarchy
├── auth/             TokenProvider
├── azure/            AzureRunner + resources / files / executor / entitlements
├── cli/              argparse parser + dict dispatch + command handlers
├── config/           Frozen-dataclass models + YAML loader
├── kusto/            KustoIngestor, TelemetryPayload, schema names
├── local/            LocalRunner subprocess wrapper
├── scaffolding/      Scaffolder + bundled .tpl templates
├── telemetry/        Centralised logger configuration
└── testing/          BaseService, ServiceRegistry, RequestContext,
                      PerformanceUser, _collector
```

### Removed modules / classes

* `osdu_perf.operations.*` (entire subtree, including
  `input_handler.py` at 901 LOC, `service_orchestrator.py`,
  `auth.py`, `entitlement.py`, `azure_test_operation/*`,
  `local_test_operation/*`, `init_operation/*`).
* `osdu_perf.locust_integration.user_base` (419 LOC; logic split across
  `testing/user.py`, `testing/_collector.py`, `kusto/ingestion.py`).
* `osdu_perf.utils.*` (`environment.py`, `logger.py`).
* CLI `command_base.py`, `command_factory.py`, `command_invoker.py`,
  `main.py`, `arg_parser.py`, and per-command `*_command.py` modules.
* Classes: `AzureTokenManager`, `InputHandler`, `ServiceOrchestrator`,
  `AzureLoadTestRunner` (old god-object), `InitRunner`,
  `LocalTestRunner`, `Entitlement` (module-level), `Command`,
  `CommandFactory`, `CommandInvoker`, `detect_environment`.

### Added modules / classes

* `config/_models.py`: `AppConfig`, `OsduEnv`, `AzureLoadTest`,
  `KustoConfig`, `TestMetadata`, `TestDefaults`,
  `PerformanceProfile`, `Scenario`, `WaitTime` — all frozen
  dataclasses. Merging logic (`resolved_settings`) lives on `AppConfig`.
* `config/_loader.py`: `load_config(search_root=None)` walks up from cwd
  looking for `config/system_config.yaml` + `config/test_config.yaml`.
  `_ingest_from_cluster` / `_cluster_from_ingest` auto-derive the missing
  Kusto URI.
* `auth/_token.py`: `TokenProvider` with a per-`app_id` cache and a
  shell-out to `az account get-access-token --resource`.
* `testing/context.py`: `RequestContext` dataclass holding
  `host / partition / app_id / bearer_token / test_run_id / scenario /
  config / _hostname / _counter`; `from_environment(config, scenario)`
  builds one per Locust user.
* `testing/services.py`: `ServiceRegistry.discover(client, root)` scans
  `perf_*_test.py`, instantiates `BaseService` subclasses, logs via the
  `osdu_perf` logger hierarchy (no `print`).
* `testing/_collector.py`: `collect_payload(environment, ctx)` produces a
  `TelemetryPayload`, preserving the old Kusto column schema
  (Service/Name/Method/Requests/Failures/all percentiles 50th–999th/etc).
* `kusto/ingestion.py`: `KustoIngestor(config, *, use_managed_identity)`
  with lazy client creation and MULTIJSON ingestion.
* `azure/resources.py`: `AzureResourceProvisioner` raises
  `AzureResourceError` (not `RuntimeError`) when a resource is missing
  and `allow_resource_creation=false`.
* `azure/files.py`: `TestFileUploader.discover` + `upload`; locustfile
  sorted last as `JMX_FILE`, rest as `ADDITIONAL_ARTIFACTS`.
* `azure/executor.py`: `TestExecutor.start / status / wait / stop`;
  enforces the 50-character `displayName` limit.
* `azure/entitlements.py`: `EntitlementProvisioner` resolves the ALT
  managed identity's `appId` via Microsoft Graph, then adds it to the
  three standard OSDU groups.
* `azure/runner.py`: `AzureRunner(config)` orchestrator with an
  `AzureRunInputs` dataclass; injects the same ALT environment variables
  as v1 (`LOCUST_HOST`, `PARTITION`, `APPID`, `LOCUST_USERS`,
  `LOCUST_SPAWN_RATE`, `LOCUST_RUN_TIME`, `AZURE_LOAD_TEST`,
  `OSDU_ENV`, `OSDU_TENANT_ID`, `TEST_RUN_ID_NAME`, `LOCUST_TAGS`,
  `ADME_BEARER_TOKEN`, `LAST_TEST_TIME_STAMP`). Data-plane scope
  preserved (`https://cnt-prod.loadtesting.azure.com/.default`).
* `local/_runner.py`: `LocalRunner` builds a subprocess `locust` command
  from a `LocalRunInputs` dataclass.
* `scaffolding/_project.py`: `Scaffolder(target, force=False)` plus
  `SAMPLES` registry and `available_samples()`. Templates live in
  `scaffolding/templates/*.tpl` and are read via `importlib.resources`.
* `cli/_parser.py` + `cli/_dispatch.py`: argparse definition + dict-based
  dispatcher. Replaces the Command/Factory/Invoker trio.
* `telemetry/__init__.py`: `configure(level, verbose=False)` +
  `get_logger(name)`. Logger hierarchy under `osdu_perf`, stderr handler,
  `propagate=False`.

### Code-quality cleanups

* Zero `print()` calls in library code — everything routes through
  `osdu_perf.telemetry.get_logger`.
* No emoji in log messages (they broke non-UTF-8 terminals).
* Dead code removed: `arg_parser._add_config_arg` with its `if False:`
  block, duplicate imports in the old `user_base.py`, unused helpers in
  `utils/environment.py`.
* All mutable shared state is now `frozen=True` dataclasses.

### Tests

* 138 legacy tests removed (they exercised classes that no longer exist).
* 14 new unit tests covering config loading, CLI parser shape, scaffolder
  output, `ServiceRegistry` discovery, and `TokenProvider` caching.
* pytest runs without coverage plugins by default; `addopts = ""`.

### Tooling

* `ruff.toml` with `select = ["E", "F", "I", "B", "UP", "SIM"]`,
  `line-length = 100`, `target-version = "py310"`. Clean across both
  `osdu_perf/` and `tests/`.
* `pyproject.toml` dev extras trimmed to `pytest`, `pytest-cov`, `ruff`,
  `build`, `twine`. `black`, `flake8`, `mypy`, `pytest-asyncio` removed.
* `MANIFEST.in` updated to ship `scaffolding/templates/*.tpl`.
* Console-script entry point is `osdu_perf.cli:main` (was
  `osdu_perf.cli.main:main`).

### Docs

* `Readme.md` rewritten around the new quick-start flow.
* `CHANGES.md` (this file).
* `CONTRIBUTING.md` references the new layout.

---

## 1.x

See Git history for details.
