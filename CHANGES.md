# Changelog

## 2.2.7 — Collision-free test run ids, action-aware correlation ids, web-UI label overrides

### Added

* **`--osdu-extra-labels` flag on the Locust swarm form** (and the
  matching `OSDU_PERF_EXTRA_LABELS_OVERRIDE` env var). Accepts either
  a JSON object (`{"image":"opt-1.2.3"}`) or comma-separated
  `key=value` pairs. Values are merged on top of the deploy-time
  `OSDU_PERF_EXTRA_LABELS` bag for the next swarm only — so you can
  redeploy a chart once and iterate on image / build labels purely
  from the web UI.
* **`BaseService.new_correlation_id(action='')`** — thread-safe
  correlation-id helper available on every test class. The generated
  id is `<test_run_id>[-<action>]-<host4>-<counter>` (or
  `<action>-<host4>-<counter>` when no test_run_id is set). Use the
  optional `action` segment to tag individual request kinds (e.g.
  `"put"`, `"get"`, `"search"`) so you can filter OSDU service-side
  logs down to a specific API call within a single run.
* **`storage_put_records` sample** (`osdu_perf init
  --sample=storage_put_records`). Scaffolds a Storage PUT-records
  workload: legaltag + schema/kind bootstrap in `prehook`, then
  single-record upserts in the hot loop.

### Changed

* **Test run id scheme is now clock-independent.** The old format
  `<test_name>-<prefix>-<UTCts>` has been replaced with
  `<test_name>-<prefix>-<host4>-<rand8>`, where `host4` is the last
  4 chars of the short hostname (on AKS, the Locust master pod
  suffix) and `rand8` is 8 hex chars from `secrets.token_hex(4)`.
  Rationale: back-to-back web-UI swarms inside the same second were
  colliding on the old timestamp-based id; the new id is guaranteed
  unique across pods and cycles without any clock precision
  assumptions.
* **`RequestContext.new_correlation_id` now accepts an optional
  `action`** and uses `host4` instead of the full hostname, keeping
  correlation ids short enough for log-index-friendly filtering.

## 2.2.5 / 2.2.6 — Internal-only

Published tags for dogfooding the 2.2.7 changes on the v3 matrix
clusters. No user-visible API changes beyond those documented under
2.2.7.

## 2.2.4 — One-shot setup hooks now actually fire once per worker

### Fixes

* **`ServiceRegistry.discover()` re-executed the test file on every
  `User.on_start`**, silently resetting any class-level state (e.g.
  one-shot setup guards) and turning a single intended setup call into
  one call per spawned user. The registry now caches the loaded module
  by absolute path in a class-level dict, so repeated `discover()`
  invocations inside the same process reuse the already-executed
  module. Tests that rely on `_setup_done = True` class attributes (or
  any other module-level state) now behave as documented.
* **`storage_get_record_by_id` sample**: the prehook guard is now
  stashed on the `osdu_perf` module (loaded exactly once per process),
  not on the test class. Setup runs **once per worker process**
  regardless of the user count — a 500-user run with 10 workers does
  10 legaltag/record upserts, not 500.

## 2.2.3 — New `storage_get_record_by_id` sample

### Added

* **`osdu_perf init --sample=storage_get_record_by_id`** scaffolds a
  Storage GET-Record-by-ID workload. The sample's `prehook` runs
  exactly once per worker process (guarded by a class-level lock) and:
  1. `POST /api/legal/v1/legaltags` to create
     `<partition>-public-usa-check-1` (409 = already exists, treated
     as success).
  2. `PUT /api/storage/v2/records` to upsert one or more
     `master-data--Well` records with ids
     `<partition>:master-data--Well:perf{1..N}`.

  After setup, `execute` issues `GET /api/storage/v2/records/<id>` on
  a randomly chosen seeded id. Configurable via env vars
  `STORAGE_LEGALTAG_NAME`, `STORAGE_RECORD_KIND`,
  `STORAGE_RECORD_ID_PREFIX`, `STORAGE_RECORD_COUNT`.
* Setup calls go to Locust under separate stat names
  (`storage_get_record_by_id__setup_legaltag` /
  `__setup_records`) so they don't pollute GET latency stats.

## 2.2.2 — Bootstrap a fresh AKS cluster without manual SA YAML

### Added

* **`--create-service-account` flag on `osdu_perf run k8s`** (and matching
  `aks.create_service_account: true` in `azure_config.yaml`). When set,
  the bundled Helm chart creates the `osdu-perf-runner` ServiceAccount in
  the target namespace with the `azure.workload.identity/client-id`
  annotation derived from `aks.workload_identity_client_id`. Use this on a
  brand-new cluster where the SA does not yet exist; on shared clusters
  the default (`false`) keeps the chart from touching an SA you
  already manage.
* **Fail-fast preflight check** in `K8sRunner`. Before the helm install,
  the runner now `kubectl get serviceaccount`s the configured SA. If it
  is missing and `--create-service-account` was not requested, the run
  aborts immediately with a copy-pasteable remediation block — instead
  of letting helm hang for the 5-minute `--wait --timeout` only to
  surface a cryptic `serviceaccount "..." not found` ReplicaSet event.

### Changed

* `K8sRunInputs` gained a `create_service_account: bool` field;
  `K8sRunner._build_values` now plumbs that through to
  `serviceAccount.create` in the chart values.
* `AksConfig` gained a `create_service_account: bool` field; loader
  reads the new YAML key, scaffolding template documents it.
* Readme “Cluster-side prerequisites” section updated to mention the
  flag and the new bootstrap path.

## 2.2.1 — Bug fixes on top of 2.2.0

### Fixes

* **No Kusto rows ingested for distributed `run k8s` runs.** In
  distributed mode the master runs no Users, so
  `PerformanceUser._context` stayed `None` and `_on_test_stop` silently
  returned. The `test_start` listener now builds the context eagerly
  on master/local runners (workers still build lazily on first User
  spawn).
* **`osdu_perf run local` failed with "Locust is not installed"**
  outside an activated venv. The runner now invokes
  `sys.executable -m locust` instead of bare `locust` so the right
  interpreter is always used.

## 2.2.0 — Helm-chart–backed AKS runner

### Highlights

* `osdu_perf run k8s` now deploys via a **bundled Helm chart**
  (`osdu_perf/k8s/chart/`) instead of hand-rolled
  `string.Template` YAML. One `helm upgrade --install` owns the
  ServiceAccount, ConfigMap, master Service + Deployment/Job, worker
  Deployment/Job, and — new — the resource that exposes the Locust web
  UI outside the cluster.
* New `aks.ingress:` config block (see Readme). `type: istio` renders
  a `VirtualService` bound to an existing `Gateway`; `type: ingress`
  renders a standard Kubernetes `Ingress`; `type: none` (default)
  keeps the UI cluster-internal (use `kubectl port-forward`).
* The master auto-applies `--web-base-path=<path_prefix>` when
  `ingress.type != none`, so the UI works behind a sub-path route
  without extra flags.
* Adhoc YAML samples removed — the chart is the single source of
  truth for what runs on the cluster.

### Breaking

* **New prerequisite**: `helm` (v3+) must be on the operator's
  `PATH`. `docker`, `az`, and `kubectl` requirements are unchanged.
* Removed internal module `osdu_perf.k8s.manifests`
  (`stage_build_context` now lives in `osdu_perf.k8s.builder`).

### Added

* `osdu_perf.config.AksIngress` dataclass (exposed from
  `osdu_perf.config`) mirroring the new `aks.ingress:` YAML block.
* `tests/unit/test_k8s_chart.py` covering values-dict rendering and
  (when `helm` is on `PATH`) a live `helm template` round-trip.

## 2.1.1 — Bug fixes for k8s telemetry

### Fixes

* **Duplicate Kusto summary rows** in distributed (master + N workers)
  runs. `test_stop` was firing on every worker *and* the master, each
  ingesting their partial view. Now workers skip ingestion (detected via
  `type(environment.runner).__name__ == "WorkerRunner"`); the master
  remains the sole ingestor with aggregated stats.
* **`--label KEY=VALUE` missing from Kusto `Labels` column** for
  `run k8s`. The CLI merged labels into runner inputs but never
  propagated them into the pod. The k8s ConfigMap now carries
  `OSDU_PERF_EXTRA_LABELS` (JSON, YAML-escaped), which
  `RequestContext.labels()` already consumes.
* **`Users`, `SpawnRate`, `RunTimeSeconds` reported as `0`** in Kusto
  for web-UI and adhoc runs where the ConfigMap didn't set
  `OSDU_PERF_PROFILE_*` env vars. The collector now reads live values
  from `environment.runner.target_user_count` / `runner.spawn_rate` /
  `parsed_options.run_time` with fallback to the env-var-derived
  `RequestContext` fields.
* **`TestDurationSeconds=0`** when `stats.total.last_request_timestamp`
  is `None` (e.g. a failed run with no successful requests). Falls
  back to the observed wall-clock duration from `runner.start_time`.
* **`RunTimeSeconds` column in web-UI mode** now reports the observed
  duration when no `--run-time` was supplied, instead of `0`.

## 2.1.0 — AKS runner, web-UI mode, in-browser overrides

Additive, backward-compatible enhancements on top of `2.0.0`. No
existing command changes behaviour unless you opt in.

### CLI — new subcommand `osdu_perf run k8s`

Build the test project as a container image, push it to Azure Container
Registry, then deploy a distributed Locust run (1 master + N-1 workers,
where N = `engine_instances`) on AKS using Workload Identity for OSDU +
Kusto auth. New flags specific to `run k8s`:

| Flag                | Purpose                                                                |
| ------------------- | ---------------------------------------------------------------------- |
| `--namespace NAME`  | Override `aks.namespace` from `azure_config.yaml` (default `perf`).    |
| `--image-tag TAG`   | Override the auto-generated image tag (default: derived from run name).|
| `--no-build`        | Skip docker build; reuse the image already in ACR.                     |
| `--no-push`         | Build the image but do not push to ACR (local docker only).            |
| `--no-logs`         | Apply manifests then exit; do not stream master logs.                  |
| `--web-ui`          | Web-UI mode (see below).                                               |

New required `azure_config.yaml` block:

```yaml
aks:
  subscription_id: <sub-guid>
  resource_group: <rg>
  cluster_name: <aks-name>
  namespace: perf
  service_account: osdu-perf-runner
  workload_identity_client_id: <uami-client-id>
  web_ui: false                         # default; CLI --web-ui overrides
  container_registry:
    name: myacr                         # short ACR name (used for `az acr login`)
    image_repository: osdu-perf
```

Cluster-side prerequisites (one-time): AKS Workload Identity + OIDC
issuer enabled, a UAMI with `AcrPull` on the registry + `Database User`
on Kusto + the OSDU app role(s) the test calls, and a federated
credential on the UAMI bound to
`system:serviceaccount:<namespace>:<service_account>`.

### CLI — web-UI mode for k8s runs (`--web-ui`)

`osdu_perf run k8s --web-ui` keeps the master pod alive serving
Locust's web UI on port 8089 (`--web-host=0.0.0.0`, no `--headless`,
no `--run-time`). Workers attach as usual; the operator drives runs
from the browser. Pair with `kubectl port-forward` or an Istio
VirtualService routing a sub-path (`--web-base-path=/locust`) to the
master service.

Each click of **Start swarming** in the browser:

1. Resets per-endpoint accumulators on every worker so repeat runs
   each produce a distinct Kusto telemetry payload.
2. Generates a fresh `<test_name>-<prefix>-<UTCts>` test-run id and
   ingests it as a separate row at test-stop.

### CLI — in-browser overrides (web-UI mode)

The Locust swarm form now exposes two custom fields, auto-rendered
from CLI options registered via `@events.init_command_line_parser`:

| Field            | Backing CLI / env                                  |
| ---------------- | -------------------------------------------------- |
| `Osdu test name` | `--osdu-test-name` / `OSDU_PERF_TEST_NAME`         |
| `Osdu test run id prefix` | `--osdu-test-run-id-prefix` / `OSDU_PERF_TEST_RUN_ID_PREFIX` |

Defaults populate from the pod's environment, so leaving them alone
behaves exactly as today. Change either, click **Start swarming**, and
the next run's Kusto `TestRunId` reflects the new values without
restarting any pod.

### CLI — `--azure-config PATH`

New flag on every `run` subcommand. Pick a non-default
`azure_config.yaml` (relative to `--directory` or absolute). One
project can hold per-cluster configs, e.g.:

```
config/azure_config.yaml          # AKS1
config/azure_config_aks2.yaml     # AKS2
config/azure_config_aks3.yaml     # AKS3
```

For `run k8s`, the same path is bundled into the image and read by
the pod via the `OSDU_PERF_AZURE_CONFIG` env var (also honoured by
`load_config()`).

### Test-run id reshape

The generated test-run id (Kusto `TestRunId` column, Locust env var,
correlation-id base) drops the leading `<scenario>_` segment and
collapses to:

```
<test_name>-<prefix>-<UTC_YYYYMMDDHHMMSS>
```

This matches the AKS pod/job naming and keeps Kusto rows easy to
group by `TestName`. The CLI's pre-computed `test_run_id_prefix` is
folded as `<test_name>-<configured_prefix>` so banner + Kusto + in-pod
generated id all agree. `_generate_test_run_id` is idempotent — if
the prefix already starts with the test name it is not duplicated.

### CLI — load-shape overrides

New flags on `run local`, `run azure`, and `run k8s` that override
individual fields of the resolved profile:

| Flag                    | Overrides                                           |
| ----------------------- | --------------------------------------------------- |
| `--users N`             | `profile.users`                                     |
| `--spawn-rate N`        | `profile.spawn_rate`                                |
| `--run-time DURATION`   | `profile.run_time`                                  |
| `--engine-instances N`  | `profile.engine_instances` (worker pod count on k8s)|

Mix and match — any flag you pass replaces that single field, the rest
come from the profile.

### CLI — test run id prefix

`test_run_id_prefix` is now a top-level field in
`config/test_config.yaml` (default `perf`). Per-invocation override:
`--test-run-id-prefix TAG`.

### CLI — stable ALT test id via `test_name`

Every `osdu_perf run azure` invocation used to create a brand-new ALT
test definition, cluttering the portal. Now the ALT *test id* is stable
per `(scenario, test_name)` pair and **reused across runs** — each
invocation nests a new *run* under the same test.

* New config field: `run_scenario.test_name:` in
  `config/test_config.yaml`.
* New CLI flag: `--test-name NAME` (overrides the config).
* Defaults to the scenario name when unset.

Generated identifiers:

```
ALT Test id:     <scenario>_<test_name>                     # stable
Test run id:     <test_name>-<prefix>-<UTC_timestamp>       # unique
```

### CLI — extra labels

`--label KEY=VALUE` (repeatable) merges extra telemetry labels on top
of the resolved set (`labels:` + `scenario_defaults.<scenario>.metadata`
+ `run_scenario.labels`). Propagated to every Kusto row and to Locust
via the `OSDU_PERF_EXTRA_LABELS` env var.

```bash
osdu_perf run azure --scenario search_query \
  --label build=42 --label region=eastus --label commit=$GITHUB_SHA
```

### CLI — richer startup summary

`osdu_perf run azure` and `run k8s` print a single readable block on
startup with scenario, test name, profile, Test ID, Test Run ID, load
shape, host/partition/app id, merged labels, ALT or AKS resource
identifiers, and a deep-link portal URL.

### Scaffolding

Only the `search_query` sample is bundled now — `storage_crud` and
`schema_browse` (and the generic `perf_service_test.py.tpl` fallback)
are removed. The default for `osdu_perf init --sample` is
`search_query`.

The `search_query` sample issues a POST to `/api/search/v2/query`
with a random OSDU record id, configurable via `SEARCH_QUERY_KIND` /
`SEARCH_QUERY_RECORD_ID_PREFIX` / `_MIN` / `_MAX` env vars.

### Bug fixes

* `LocalRunner` no longer injects `--tags <scenario>` into the Locust
  subprocess; that filtered out the generic scaffolded `@task` and
  raised "No tasks defined on OsduUser".
* `PerformanceUser.context` attribute renamed to `osdu_context` (7
  call-sites) so it no longer shadows Locust's `HttpUser.context()`
  method, which Locust itself calls during `self.client.post(...)` —
  previously raised "'RequestContext' object is not callable".
* Azure data-plane client is now constructed with the hostname only.
  The `azure-developer-loadtesting` SDK formats its base URL as
  `https://{endpoint}`, so prepending `https://` to the data-plane URI
  produced `https://https://<host>` and failed TLS verification with a
  hostname-mismatch error.
* Locust scripts are now uploaded with ALT file type `TEST_SCRIPT`
  (not `JMX_FILE`, which is JMeter-only). Required bump of
  `azure-developer-loadtesting` to `>=1.2.0b1`.
* Wheel bundling: `*.whl` files in the project directory are now
  discovered and uploaded with the test, so local-development copies
  of `osdu_perf` can be installed on the ALT engine without publishing
  to PyPI.

---

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

* `init` now takes `--sample=<name>` (default `search_query`), not a
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
│   ├── azure_config.yaml
│   └── test_config.yaml
├── locustfile.py
├── perf_<sample>_test.py
├── requirements.txt
└── README.md
```

Bundled samples: `search_query`. Run `osdu_perf samples` to list them.

### Configuration

Two typed YAML files with a clean split between platform and test:

* `config/azure_config.yaml` — **platform only**, with two independent
  top-level sections:
  * `azure_load_test` — subscription, resource group, location,
    `allow_resource_creation`, and ALT resource `name`. Used only by
    `osdu_perf run azure`.
  * `kusto_export` — optional telemetry sink (`cluster_uri` or
    `ingest_uri`, plus `database`). Used by **both** `osdu_perf run
    local` and `osdu_perf run azure`.
* `config/test_config.yaml` — **everything about the test**. Shape:
  * `osdu_environment` — host, partition, app_id of the target OSDU
    instance.
  * `labels` — free-form passthrough attached verbatim to every Kusto
    telemetry row. Renamed from `test_metadata`.
  * `profiles` — named load shapes. Canonical naming convention
    `U<users>_T<duration>` (e.g. `U100_T15M`). Each profile carries
    `users`, `spawn_rate`, `run_time`, `engine_instances`, `wait_time`.
  * `scenario_defaults` — per-scenario default profile + metadata.
    Required sub-key: `profile:` (must reference a `profiles:` key).
    Optional: `metadata:` (merged into telemetry labels).
  * `run_scenario` — the default invocation when `osdu_perf run` is
    called without `--scenario`. Can also override the profile and
    append extra labels — those only apply when `run_scenario` is the
    source of the scenario.

Resolution for a single run:

* **Scenario**: `--scenario` CLI flag → `run_scenario.scenario` → error.
* **Profile**: `--profile` CLI flag → (if scenario came from
  `run_scenario`) `run_scenario.profile` →
  `scenario_defaults[scenario].profile` → error listing available
  profiles.
* **Telemetry labels** (merged, last wins): top-level `labels` ←
  `scenario_defaults[scenario].metadata` ← (if scenario came from
  `run_scenario`) `run_scenario.labels`.

Previous v2.0.0 concepts that are gone:

* `scenarios:` block as a registry — removed. Scenarios are Python
  files under `perf_tests/`; the YAML only declares *defaults* for
  them.
* `test_settings:` top-level defaults — removed. Profiles are the only
  source of load-shape values.
* `test_metadata:` — renamed to `labels:`.
* `profiles.default` as implicit fallback — removed. Either provide
  `--profile`, `scenario_defaults[name].profile`, or
  `run_scenario.profile`; otherwise `osdu_perf` errors with the list
  of available profiles.
* Scenario-level load-shape overrides (`users`, `spawn_rate`,
  `run_time`) — removed. Pick a different profile instead.

`system_config.yaml` was renamed to `azure_config.yaml`.

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
* `ScenarioNotFoundError` — no scenario specified (neither CLI nor
  `run_scenario.scenario`).
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
  `KustoConfig`, `PerformanceProfile`, `ScenarioDefault`, `RunScenario`,
  `ResolvedRun`, `WaitTime`.
  `PerformanceProfile`, `Scenario`, `WaitTime` — all frozen
  dataclasses. Merging logic (`resolved_settings`) lives on `AppConfig`.
* `config/_loader.py`: `load_config(search_root=None)` walks up from cwd
  looking for `config/azure_config.yaml` + `config/test_config.yaml`.
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
