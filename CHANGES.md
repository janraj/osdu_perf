# Changelog

## 3.0.0 — Full rewrite

Complete refactor for open-source release quality. No backward compatibility
with v2.

### New package layout

```
osdu_perf/
├── auth/            TokenProvider (replaces AzureTokenManager)
├── azure/           AzureRunner + resource/file/executor/entitlements helpers
│                    (replaces operations/azure_test_operation/*)
├── cli/             argparse CLI with a simple dict-based dispatcher
│                    (replaces Command/Factory/Invoker pattern)
├── config/          Typed frozen-dataclass models + YAML loader
│                    (replaces the 901-line InputHandler)
├── errors.py        Typed exception hierarchy (OsduPerfError, ConfigError,
│                    ScenarioNotFoundError, AuthError, AzureResourceError,
│                    ScaffoldError)
├── kusto/           KustoIngestor + TelemetryPayload + schema names
│                    (extracted from user_base.py)
├── local/           LocalRunner subprocess wrapper
├── scaffolding/     Scaffolder + bundled sample templates
├── telemetry/       Logger configuration
└── testing/         PerformanceUser, BaseService, ServiceRegistry,
                     RequestContext
```

### CLI redesign

```bash
# v2
osdu_perf init search                        # positional
osdu_perf run local --partition opendes ...

# v3
osdu_perf init --sample=search_query         # named --sample
osdu_perf run local --scenario search_query  # subcommand
osdu_perf run azure --scenario search_query
osdu_perf validate
osdu_perf samples
osdu_perf version
```

### Removed

* `osdu_perf.operations.*`
* `osdu_perf.locust_integration.*`
* `osdu_perf.utils.*`
* `AzureTokenManager`, `InputHandler`, `ServiceOrchestrator`,
  `AzureLoadTestRunner`, Command/Factory/Invoker classes,
  `detect_environment`.

### Added

* Frozen-dataclass configuration: `AppConfig`, `OsduEnv`, `AzureInfra`,
  `KustoConfig`, `TestDefaults`, `Scenario`, etc.
* `ServiceRegistry.discover(root=Path)` — explicit, test-friendly.
* Bundled sample templates shipped via `importlib.resources`.
* `ruff.toml` with sensible defaults.

## 2.0.0 — Prior v2 cleanup

See Git history for details.
