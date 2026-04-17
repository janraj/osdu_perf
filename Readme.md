# osdu_perf

Performance testing framework for OSDU APIs, built on [Locust] and
[Azure Load Testing]. Scaffolds a complete test project in one command,
runs locally for iteration, and promotes the **same** project to Azure
Load Testing for scale runs.

[Locust]: https://locust.io/
[Azure Load Testing]: https://learn.microsoft.com/azure/load-testing/

---

## 5-minute quick start

> This section is intentionally terse and copy-pasteable. Every command
> is safe to run top-to-bottom on a clean machine. Expected output is
> shown after each step.

### 1. Install

```bash
pip install osdu_perf
```

Verify:

```bash
osdu_perf version
# 2.0.0
```

### 2. Scaffold a project

```bash
mkdir my-osdu-perf && cd my-osdu-perf
osdu_perf init --sample=search_query
```

Expected output:

```
Scaffolded 'search_query' at /path/to/my-osdu-perf
```

Files created:

```
my-osdu-perf/
├── config/
│   ├── azure_config.yaml        # Azure Load Test target + Kusto export (both optional)
│   └── test_config.yaml         # OSDU env, labels, profiles, scenario defaults
├── locustfile.py                # Locust entry point
├── perf_search_query_test.py    # your service test
├── requirements.txt
└── README.md
```

### 3. Edit `config/test_config.yaml`

Open it and fill in the three required fields under `osdu_environment`
(test settings and scenarios already have sensible defaults):

```yaml
osdu_environment:
  host: "https://your-osdu-host.com"
  partition: "opendes"
  app_id: "<azure-ad-app-id>"
```

### 4. Sign in to Azure (needed for token acquisition)

```bash
az login
az account set --subscription <your-subscription-id>
```

### 5. Validate

```bash
osdu_perf validate
```

Expected output:

```
Configuration loaded successfully.
  host:      https://your-osdu-host.com
  partition: opendes
  app_id:    <azure-ad-app-id>
  profiles:  u100_t15m, u200_t30m, u50_t15m
  scenario defaults: search_query
  run_scenario: search_query (profile=-)
```

### 6. Run locally

```bash
osdu_perf run local --scenario search_query
```

Locust's web UI opens at <http://localhost:8089>. For a headless CI run:

```bash
osdu_perf run local --scenario search_query --headless
```

### 7. (Optional) Run on Azure Load Testing

Add an `azure_load_test` block to `config/azure_config.yaml`:

```yaml
azure_load_test:
  subscription_id: "<subscription-id>"
  resource_group: "osdu-perf-rg"        # must already exist
  location: "eastus"
  name: "osdu-perf-alt"                 # existing ALT resource
```

Then:

```bash
osdu_perf run azure --scenario search_query
```

Expected output (last line):

```
Started test run: search_query_perf_search_query_20260417120000
```

That's it. You now have a running OSDU performance test.

---

## Prerequisites

| Requirement      | Minimum     | Notes                                            |
| ---------------- | ----------- | ------------------------------------------------ |
| Python           | 3.10        | 3.11/3.12 recommended                            |
| Azure CLI (`az`) | 2.50+       | Used for token acquisition (`az login` required) |
| OSDU access      | —           | Valid `host`, `partition`, and AAD `app_id`      |
| Azure Load Test  | *(optional)*| Only if you use `osdu_perf run azure`            |

---

## Installation

```bash
# Stable release
pip install osdu_perf

# Development install from a clone
git clone https://github.com/janraj/osdu_perf.git
cd osdu_perf
pip install -e ".[dev]"
```

---

## Writing a service test

Every file matching the glob `perf_*_test.py` next to `locustfile.py` is
auto-discovered by `ServiceRegistry`. A service must subclass
`BaseService` and implement four methods.

```python
# perf_storage_test.py
from osdu_perf import BaseService


class StorageService(BaseService):
    """Minimal Storage-API performance test."""

    def provide_explicit_token(self) -> str:
        # Return "" to use the token from TokenProvider.
        return ""

    def prehook(self, headers=None, partition=None, host=None) -> None:
        # Optional: seed data, create parents, etc.
        pass

    def execute(self, headers=None, partition=None, host=None) -> None:
        self.client.get(
            f"{host}/api/storage/v2/records/opendes:test:1",
            name="storage_get_record",   # groups requests in Locust stats
            headers=headers,
        )

    def posthook(self, headers=None, partition=None, host=None) -> None:
        # Optional: cleanup.
        pass
```

### What the framework injects for you

| Argument    | Source                                                 |
| ----------- | ------------------------------------------------------ |
| `headers`   | `Authorization`, `data-partition-id`, `Correlation-Id` |
| `partition` | `osdu_environment.partition` (or `--partition`)        |
| `host`      | `osdu_environment.host` (or `--host`)                  |

`self.client` is Locust's `HttpSession` — it records timings and errors
automatically.

---

## Configuration reference

Two YAML files under `config/` drive everything. The loader walks up
from the current working directory looking for them.

### `config/azure_config.yaml` — platform only

Describes **where** tests run and **where** telemetry goes. Both
sections are optional and independent.

* `azure_load_test` — target for `osdu_perf run azure`. Not used by
  `run local`.
* `kusto_export` — optional telemetry sink. Used by **both**
  `run local` and `run azure`; when configured, every completed run
  ingests a summary row into the database.

```yaml
# Required only for `osdu_perf run azure`.
azure_load_test:
  subscription_id: "<subscription-id>"
  resource_group: "osdu-perf-rg"
  location: "eastus"
  allow_resource_creation: false   # true lets osdu_perf create RG + ALT
  name: "osdu-perf-alt"

# Optional telemetry sink — applies to local and azure runs alike.
# Provide EITHER cluster_uri OR ingest_uri (the other is derived).
kusto_export:
  cluster_uri: "https://<cluster>.<region>.kusto.windows.net"
  database: "osdu-perf"
```

### `config/test_config.yaml` — everything about the test

```yaml
# Required: OSDU instance coordinates.
osdu_environment:
  host: "https://your-osdu-host.com"
  partition: "opendes"
  app_id: "<azure-ad-app-id>"

# Free-form labels copied verbatim to every Kusto telemetry row.
# The framework does not interpret any key here.
labels:
  version: "25.2.35"
  build_id: "ci-4321"

# Named load shapes. Naming convention: U<users>_T<duration>.
profiles:
  U50_T15M:  { users: 50,  spawn_rate: 5,  run_time: "15m" }
  U100_T15M: { users: 100, spawn_rate: 10, run_time: "15m" }
  U200_T30M: { users: 200, spawn_rate: 20, run_time: "30m", engine_instances: 2 }

# Per-scenario defaults. Scenarios themselves are the Python files
# under perf_tests/ — this block is NOT a registry, just defaults.
scenario_defaults:
  search_query:
    profile: U100_T15M
    metadata:
      scenario_kind: "query"
  storage_crud:
    profile: U50_T15M

# Default invocation when `osdu_perf run` is called WITHOUT --scenario.
# All keys inside apply only when this block supplies the scenario.
run_scenario:
  scenario: search_query
  profile: U200_T30M        # optional; overrides scenario_defaults.<scenario>.profile
  labels:                    # optional; merged on top of top-level labels
    triggered_by: "nightly-ci"
```

### Resolution

For a single run, `osdu_perf` picks three things:

* **Scenario**: `--scenario` CLI flag → `run_scenario.scenario` → error.
* **Profile**: `--profile` CLI flag → (if scenario came from
  `run_scenario`) `run_scenario.profile` →
  `scenario_defaults[scenario].profile` → error listing available
  profiles.
* **Telemetry labels** (merged, last wins): top-level `labels` ←
  `scenario_defaults[scenario].metadata` ← (if scenario came from
  `run_scenario`) `run_scenario.labels`.

`labels` is pure passthrough — it never affects what gets run, only
what gets logged to Kusto.

---

## CLI reference

All commands accept `-v` / `--verbose` for debug logging and full
tracebacks.

### `osdu_perf init`

Scaffold a new project.

```bash
osdu_perf init --sample=<name> [--directory=PATH] [--force] [--list-samples]
```

* `--sample=<name>`: one of `storage_crud`, `search_query`,
  `schema_browse` (default `storage_crud`).
* `--directory=PATH`: target directory (default `.`).
* `--force`: overwrite existing files.
* `--list-samples`: print available samples and exit.

### `osdu_perf samples`

List bundled samples:

```
storage_crud          Storage CRUD
search_query          Search Query
schema_browse         Schema Browse
```

### `osdu_perf validate`

Loads both YAML files and prints the resolved environment. Exits
non-zero on any parse/validation error.

```bash
osdu_perf validate [--directory=PATH]
```

### `osdu_perf run local`

Spawn Locust as a subprocess.

```bash
osdu_perf run local \
  [--scenario=<name>]      \
  [--profile=<name>]       \
  [--users=N]              \
  [--spawn-rate=N]         \
  [--run-time=DURATION]    \
  [--engine-instances=N]   \  # ignored by `run local`
  [--host=URL]             \
  [--partition=ID]         \
  [--app-id=GUID]          \
  [--bearer-token=TOKEN]   \
  [--directory=PATH]       \
  [--headless]
```

* `--scenario` *(optional)* — when omitted, falls back to
  `run_scenario.scenario` in `test_config.yaml`.
* `--profile` *(optional)* — overrides any default coming from
  `scenario_defaults.<scenario>.profile` or `run_scenario.profile`.
* `--users`, `--spawn-rate`, `--run-time`, `--engine-instances`
  *(optional)* — per-invocation overrides that win over the resolved
  profile. Mix and match: any flag you pass replaces that single field,
  the rest come from the profile. `--engine-instances` is ignored by
  `run local`.
* `--headless` — run without the Locust web UI (for CI).
* `--bearer-token` / `ADME_BEARER_TOKEN` env var — skip `az` and use a
  pre-acquired token.

### `osdu_perf run azure`

Create an ALT test, upload files, provision OSDU entitlements for the
ALT managed identity, start the run.

```bash
osdu_perf run azure \
  [--scenario=<name>]          \
  [--profile=<name>]           \
  [--users=N]                  \
  [--spawn-rate=N]             \
  [--run-time=DURATION]        \
  [--engine-instances=N]       \
  [--load-test-name=NAME]      \  # overrides azure_load_test.name
  [--host / --partition / --app-id / --bearer-token / --directory]
```

### `osdu_perf version`

Prints the installed version.

---

## Test run id

Every run gets a unique id of the form:

```
<scenario>_perf_<YYYYMMDDHHMMSS>
```

where the timestamp is UTC. The id:

* becomes the Azure Load Test `testId` / `testRunId` (slugified to
  `[a-z0-9_-]`) for `osdu_perf run azure`;
* is exported to Locust as the `TEST_RUN_ID` env var for `run local`;
* is used as the base of every request's `correlation-id` header
  (`{test_run_id}-{short-hostname}-{counter}`), so you can correlate
  OSDU service-side logs with a specific run;
* is written into every Kusto telemetry row in the `TestRunId`
  column.

You can force a custom id by setting `TEST_RUN_ID_NAME` or
`TEST_RUN_ID` in the environment before invoking `osdu_perf run` —
handy when the CI system already has a build id you want to reuse.

---

## Authentication

`TokenProvider` resolves an OSDU bearer token in this order:

1. `--bearer-token` CLI flag or `ADME_BEARER_TOKEN` env var (pass-through).
2. Managed identity, when running inside Azure Load Testing (detected
   via `AZURE_LOAD_TEST` / `LOCUST_*` env vars).
3. `az account get-access-token --resource <app_id>` — preserves the
   `aud=<app_id>` claim that OSDU expects.
4. `AzureCliCredential` fallback if `az` is not on `PATH`.

Tokens are cached per `app_id` within a process.

---

## Python API

```python
from osdu_perf import (
    __version__,       # "2.0.0"
    AppConfig,         # typed config tree
    load_config,       # walks cwd → parents for config/*.yaml
    BaseService,       # subclass this to define a test
    PerformanceUser,   # Locust HttpUser with OSDU auth built in
    ServiceRegistry,   # auto-discovers perf_*_test.py
)

config = load_config()
settings = config.resolved_settings("search_query")
print(settings.users, settings.run_time)
```

### `PerformanceUser` helpers (usable inside `@task` methods)

| Method                           | Returns                                    |
| -------------------------------- | ------------------------------------------ |
| `get_host()`                     | OSDU host URL                              |
| `get_partition()`                | data-partition-id                          |
| `get_appid()`                    | AAD app id                                 |
| `get_token()`                    | bearer token                               |
| `get_headers()`                  | dict with `Authorization` etc.             |
| `get_request_headers(extra=None)`| headers with fresh `Correlation-Id`        |
| `new_correlation_id()`           | `<run_id>-<short_host>-<counter>`          |

---

## Troubleshooting

| Symptom                                                              | Fix                                                                                                 |
| -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `error: ScenarioNotFoundError: No scenario specified ...`           | Pass `--scenario <name>`, or set `run_scenario.scenario:` in `config/test_config.yaml`.             |
| `error: AuthError: Unable to acquire token. Ensure Azure CLI ...`    | Run `az login`. Or set `ADME_BEARER_TOKEN` / pass `--bearer-token`.                                 |
| `error: AzureResourceError: Azure Load Test resource '...' missing` | Create the ALT resource, fix `azure_load_test.name`, or set `allow_resource_creation: true`. |
| `error: ConfigError: host, partition, and app_id must all be provided.` | Fill in `osdu_environment` in `test_config.yaml`, or pass `--host/--partition/--app-id`.        |
| `Locust is not installed`                                            | `pip install locust` (it's a transitive dependency, should already be present).                     |
| Tokens rejected with `aud mismatch`                                  | Do **not** pass `--scope api://<id>/.default` yourself — the framework uses `--resource <app_id>`.  |

Add `-v` to any command for full tracebacks:

```bash
osdu_perf -v run local --scenario search_query
```

---

## Architecture

```
osdu_perf/
├── auth/            TokenProvider (bearer-token acquisition)
├── azure/           AzureRunner + resources/files/executor/entitlements
├── cli/             argparse parser + dict-based dispatcher
├── config/          Frozen-dataclass models + YAML loader
├── errors.py        Typed exception hierarchy (OsduPerfError and subclasses)
├── kusto/           KustoIngestor + TelemetryPayload + schema names
├── local/           LocalRunner (subprocess wrapper around `locust`)
├── scaffolding/     Scaffolder + bundled `.tpl` templates
├── telemetry/       Centralised logger configuration
└── testing/         PerformanceUser, BaseService, ServiceRegistry,
                     RequestContext, _collector
```

See [CHANGES.md](CHANGES.md) for the full v2.0.0 rewrite notes.

---

## Contributing

```bash
git clone https://github.com/janraj/osdu_perf.git
cd osdu_perf
pip install -e ".[dev]"

# Tests + lint
pytest tests/unit -q
ruff check osdu_perf tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## For LLM agents

This section is explicitly written for automated agents scaffolding or
extending an osdu_perf project.

### Decision tree

1. **User asks to create a new OSDU perf test project**
   1. `mkdir <project>` and `cd` into it.
   2. Run `osdu_perf samples` to see available templates.
   3. Run `osdu_perf init --sample=<closest-match>`.
   4. Edit `config/test_config.yaml` — fill in `host`, `partition`,
      `app_id`.
   5. Run `osdu_perf validate`; resolve any `ConfigError`.
   6. Run `osdu_perf run local --scenario <sample> --headless` for a
      smoke test.

2. **User asks to add a new API test**
   1. Create `perf_<service>_test.py` alongside `locustfile.py`.
   2. Subclass `osdu_perf.BaseService`. Implement all four methods
      (`provide_explicit_token`, `prehook`, `execute`, `posthook`).
   3. In `execute`, call `self.client.get/post/put/delete(...)` with a
      stable `name=` kwarg for Locust stats grouping.
   4. Drop the new `perf_<name>_test.py` into the project root. Add an
      entry under `scenario_defaults.<name>.profile` in
      `config/test_config.yaml` so it picks up a load shape by default.
   5. Run `osdu_perf validate` then `osdu_perf run local --scenario <name>`.

3. **User asks to run on Azure Load Testing**
   1. Ensure an `azure_load_test` block exists in `azure_config.yaml`
      with valid `subscription_id`, `resource_group`, and `name`.
   2. The resource group **and** ALT resource must exist — or set
      `allow_resource_creation: true` (and have `Contributor` at
      subscription scope).
   3. `az login && az account set --subscription <id>`.
   4. `osdu_perf run azure --scenario <name>`.

### Invariants

* Never edit files under `osdu_perf/scaffolding/templates/` in a user
  project — they are package data.
* File discovery is based on the **filename** pattern
  `perf_*_test.py`. Renaming breaks auto-registration.
* Every `BaseService` subclass **must** implement all four abstract
  methods or instantiation will raise `TypeError`.
* All library errors inherit from `osdu_perf.errors.OsduPerfError`.
  CLI wrappers should catch this base class.
* Kusto table names (`LocustMetricsV2`, `LocustExceptionsV2`,
  `LocustTestSummaryV2`) are stable — do **not** rename them.

### Safe, idempotent commands

These can be run repeatedly without damage:

* `osdu_perf samples`
* `osdu_perf version`
* `osdu_perf validate`
* `osdu_perf run local --scenario <name> --headless` *(local only; no
  Azure side effects)*

### Destructive / quota-consuming commands

Require explicit user confirmation:

* `osdu_perf init` when files already exist → pass `--force` only if the
  user has asked to overwrite.
* `osdu_perf run azure` → creates/updates ALT test definitions, uploads
  files, and starts a billable run.

---

## License

MIT — see [LICENSE](LICENSE).
# osdu_perf

Performance testing framework for OSDU APIs built on top of Locust and Azure
Load Testing.

## Install

```bash
pip install osdu_perf
```

## Quick start

```bash
# 1. scaffold a test project
osdu_perf init --sample=search_query
cd .                               # edit config/test_config.yaml

# 2. validate your configuration
osdu_perf validate

# 3. run locally
osdu_perf run local --scenario search_query

# 4. (optional) run on Azure Load Testing
osdu_perf run azure --scenario search_query
```

### Available samples

```bash
osdu_perf samples
# storage_crud          Storage CRUD
# search_query          Search Query
# schema_browse         Schema Browse
```

### Writing your own service test

```python
from osdu_perf import BaseService

class StorageService(BaseService):
    def provide_explicit_token(self) -> str:
        return ""

    def prehook(self, headers=None, partition=None, host=None): ...
    def execute(self, headers=None, partition=None, host=None):
        self.client.get("/api/storage/v2/records/1", name="get_record", headers=headers)
    def posthook(self, headers=None, partition=None, host=None): ...
```

Drop the file next to ``locustfile.py`` as ``perf_storage_test.py``; the
``ServiceRegistry`` auto-discovers it.

## Architecture

```
osdu_perf/
├── auth/            Bearer-token acquisition (TokenProvider)
├── azure/           Azure Load Testing orchestration
├── cli/             argparse CLI (init, run local/azure, validate, samples)
├── config/          Typed dataclass config models + YAML loader
├── kusto/           Optional telemetry ingestion (LocustMetricsV2 etc.)
├── local/           Local Locust subprocess runner
├── scaffolding/     Bundled sample templates for `osdu_perf init`
├── telemetry/       Logger configuration
└── testing/         PerformanceUser, BaseService, ServiceRegistry
```

## CLI reference

| Command                                 | Purpose                                       |
| --------------------------------------- | --------------------------------------------- |
| `osdu_perf init --sample=<name>`        | Scaffold a new project from a sample template |
| `osdu_perf samples`                     | List available samples                        |
| `osdu_perf validate`                    | Sanity-check your `config/*.yaml` files       |
| `osdu_perf run local --scenario <s>`    | Spawn Locust locally                          |
| `osdu_perf run azure --scenario <s>`    | Provision + kick off an Azure Load Test run   |
| `osdu_perf version`                     | Print the installed version                   |

Add ``-v`` / ``--verbose`` to any command to enable debug logging and full
tracebacks.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Tests run with:

```bash
pip install -e .[dev]
pytest tests/unit -q
ruff check osdu_perf tests
```

## License

MIT. See [LICENSE](LICENSE).
