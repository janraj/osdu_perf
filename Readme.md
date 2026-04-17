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
cd .                               # edit config/system_config.yaml

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
