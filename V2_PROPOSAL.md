# osdu_perf v2 — Proposed enhancements

> **TL;DR** — v2 builds on v1's foundation to support multi-cluster
> perf campaigns end-to-end — AKS-native deployment, live web UI,
> Helm-based orchestration, and richer Kusto telemetry. Everything
> below has been validated across 4 AKS clusters running 48-run
> storage matrices unattended.

---

## 1. Where v1 left off

v1 established the core abstractions — `PerformanceUser`, `BaseService`,
Locust-based load generation, and Kusto telemetry ingestion. It works
well for single-cluster ALT runs. As we scaled to multi-cluster A/B
testing and iterative tuning, a few areas needed extension:

| Area | Opportunity |
|---|---|
| Deployment model | v1 targets ALT or bare `locust`; adding an AKS-native path would eliminate portal clicks for iterative work |
| Iteration speed | Headless-only runs mean redeploying to change load shape; a live web-UI mode would speed up tuning |
| Module structure | `input_handler.py` (900+ LOC) handles CLI, config, provisioning, and orchestration together — splitting it would make the AKS runner easier to add |
| Setup-hook execution | `ServiceOrchestrator` re-imports the test module per user, so prehooks run per-user instead of once-per-worker |
| Locust API compatibility | `PerformanceUser.context` attribute shadows `HttpUser.context()` method, causing runtime errors in some request patterns |
| Distributed telemetry | In master + worker mode, partial ingestion from each process can produce duplicates or gaps |
| Label propagation | `--label` values do not flow through to pods or Kusto rows, limiting post-hoc filtering |
| Multi-cluster configs | Running against N clusters requires N copies of the project or manual file swaps |

---

## 2. What v2 adds

### 2.1 AKS-native runner (`run k8s`)

```bash
osdu_perf run k8s --web-ui --engine-instances 3 \
  --test-name storage_baseline --label image=opt
```

One command: builds image → pushes to ACR → deploys via bundled Helm
chart (master + N workers + Istio VirtualService) → streams logs or
keeps web UI alive. No portal, no hand-rolled YAML.

**Why it matters:** ALT is great for scheduled CI runs, but iterative
perf tuning needs fast feedback loops. `run k8s` gives you a live
Locust UI on every cluster with sub-minute deploy times.

### 2.2 Web-UI mode with in-browser overrides

`--web-ui` keeps the master pod alive with Locust's browser UI. Two
custom form fields (`osdu_test_name`, `osdu_run_prefix`) let you
re-parameterise and re-run without touching any pod or config — each
"Start swarming" click generates a distinct Kusto test-run-id.

**Why it matters:** A single Helm deploy can drive dozens of
back-to-back runs with different names/prefixes. This is what powers
the automated matrix scripts that ran 48 runs across 4 clusters
unattended.

### 2.3 Bundled Helm chart with Istio ingress

The chart (`osdu_perf/k8s/chart/`) owns ServiceAccount, ConfigMap,
master + worker Deployments, Service, and VirtualService. `type: istio`
routes `https://<host>/locust/` to the master with proper
`--web-base-path`.

**Why it matters:** Eliminates the "it works on my machine" problem —
`helm upgrade --install` is idempotent and the chart is versioned with
the package.

### 2.4 Multi-config (`--azure-config`)

```bash
osdu_perf run k8s --azure-config config/azure_config_aks2.yaml \
  --host https://cluster2.example.com
```

One project directory, N cluster configs. The selected config is baked
into the container image so pods read the right one.

**Why it matters:** Multi-cluster perf campaigns (A/B testing images
across a fleet) need per-cluster configs without duplicating the entire
project.

### 2.5 CLI load-shape overrides

`--users`, `--spawn-rate`, `--run-time`, `--engine-instances` override
individual profile fields without creating a new profile entry.

**Why it matters:** Matrix scripts parameterise runs dynamically
(e.g. 60 users / 20 min) without editing YAML.

### 2.6 `--label KEY=VALUE` propagated to pods and Kusto

Labels flow from CLI → Helm values → pod env → Kusto `Labels` column.
Queryable downstream:

```kql
LocustTestSummaryV2 | where tostring(Labels.image) == "storage-opt:20260419230231"
```

**Why it matters:** Without labels, correlating Kusto rows to what was
actually running requires timestamp archaeology.

### 2.7 One-shot setup hooks that fire once per worker

`ServiceRegistry.discover()` caches the loaded module by absolute path.
Setup guards (class-level `_setup_done`) now work as documented — a
500-user / 10-worker run does 10 setup calls, not 500.

**Why it matters:** The `storage_get_record_by_id` sample creates a
legaltag and upserts records in its prehook. With module caching,
ramp-up no longer issues hundreds of redundant PUTs.

### 2.8 Correct Kusto telemetry for distributed runs

- Workers skip ingestion; master is sole ingestor with aggregated stats.
- `Users`, `SpawnRate`, `RunTimeSeconds` read from live runner state, not
  just env vars (which are zero in web-UI mode).
- `TestDurationSeconds` falls back to wall-clock when
  `last_request_timestamp` is None.

### 2.9 Bootstrap new clusters without manual SA setup

`--create-service-account` lets the Helm chart create and annotate the
Workload Identity ServiceAccount. Without the flag, a fail-fast
preflight check catches the missing SA immediately instead of letting
helm hang for 5 minutes.

---

## 3. What changed structurally

| v1 module | v2 replacement | Reason for change |
|---|---|---|
| `osdu_perf.operations.*` | Typed runners (`AzureRunner`, `K8sRunner`, `LocalRunner`) | Cleaner separation for adding AKS runner |
| `input_handler.py` (901 LOC) | `config/_loader.py` + `cli/_parser.py` | Easier to extend CLI without touching config logic |
| `ServiceOrchestrator` | `ServiceRegistry` with module caching | Fixes per-user re-import; enables once-per-worker setup |
| `command_base / factory / invoker` | `cli/_dispatch.py` dict dispatch | Simpler dispatch for `run local` / `run azure` / `run k8s` |
| `storage_crud`, `schema_browse` samples | `search_query`, `storage_get_record_by_id` | Aligned with active test scenarios |
| 138 legacy tests | 14 focused unit tests | Covering the new modules |
| `black`, `flake8`, `mypy` | Single `ruff` config | Fewer dev dependencies, consistent style |

---

## 4. Code quality

- Zero `print()` in library code — structured logging via `osdu_perf.telemetry`.
- All shared state is `frozen=True` dataclasses.
- Typed exception hierarchy (`OsduPerfError` → `ConfigError` / `AuthError` / …).
- Single `ruff.toml` config, clean across entire codebase.
- Console entry point simplified: `osdu_perf.cli:main`.

---

## 5. Backward compatibility

v2 is a **clean break** — intentionally. v1 CLI invocations will not
work as-is. However:

- `azure_config.yaml` structure is a superset (add `aks:` block, rename
  `system_config.yaml`).
- Kusto table names are unchanged (`LocustMetricsV2`,
  `LocustTestSummaryV2`).
- `run azure` still targets ALT with the same env-var contract pods
  expect.
- Existing `perf_*_test.py` files work if they subclass `BaseService`
  and implement the four abstract methods.

---

## 6. Battle-tested

This is not a theoretical rewrite. v2.2.4 has driven:

- **Search matrix**: 36 runs (4 clusters × 3 images × 3 repeats),
  12 min @ 200 users each.
- **Storage matrix v1**: 48 runs (4 clusters × 3 images × 2 cycles ×
  2 repeats), 15 min @ 100 users each — fully automated, all Kusto
  telemetry ingested and cross-referenced.
- **Storage matrix v2**: 48 runs, 20 min @ 60 users — in progress.

All driven by PowerShell scripts that call `osdu_perf run k8s` with
`--web-ui`, `--azure-config`, `--label`, `--no-build --no-push
--image-tag`, and the Locust swarm API — none of which existed in v1.

---

## 7. Why a major version bump

We considered incremental patches on v1, but the new features all
converged on the same set of internal modules. Changing them one at a
time would have broken the existing CLI and config contract just as
much as a single coordinated release — so a clean version bump felt
like the more responsible path.

| Area touched | What needed to change |
|---|---|
| **Module structure** | Adding `run k8s` required a runner abstraction that `input_handler.py` didn't have room for without splitting it. |
| **Service discovery** | Fixing per-user re-import meant replacing `ServiceOrchestrator` with `ServiceRegistry` + module caching — different interface. |
| **Base class API** | Renaming `PerformanceUser.context` → `osdu_context` to avoid shadowing Locust's method changed every test file's imports. |
| **CLI surface** | New subcommands (`run k8s`, `run azure`, `run local`) and flag naming (`--sample`, `--scenario`) made the old invocation syntax incompatible. |
| **Config model** | `aks:`, `ingress:`, and typed profile/label structures needed frozen dataclasses instead of plain dicts. |
| **Telemetry pipeline** | Correct distributed ingestion required rewriting the `test_stop` hook and collector, affecting all runners. |

Since these changes touched essentially every public surface, bundling
them into a single major release with a clear migration boundary felt
cleaner than a long series of breaking minor patches.

We'd love to walk through the changes together and incorporate any
feedback before merging.
