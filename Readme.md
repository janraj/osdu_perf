# 🔥 OSDU Performance Testing Framework

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A small, extensible Python framework for performance testing OSDU (Open Subsurface Data Universe) services. Features automatic test discovery, Azure authentication helpers, and Locust integration.

## 📋 Overview

Key features:

- ✅ Automatic test discovery (perf_*_test.py files)
- ✅ Azure AD authentication helpers (AzureTokenManager)
- ✅ Locust integration (PerformanceUser base class)
- ✅ CLI helpers to scaffold projects and templates
- ✅ Template files bundled in the package under `osdu_perf/templates`

## 🚀 Quick Start

### Installation

Install from PyPI (package name as defined in this repository):

```bash
pip install osdu_perf
```

Or install in editable mode for development:

```bash
pip install -e .[dev]
```

### CLI (scaffold a new project)

You can run the CLI either via the module or the installed console script:

- Using the module:

```bash
python -m osdu_perf.cli init storage
```

- Using the installed console script (after pip install):

```bash
osdu_perf init storage
```

The `init` command will create a `perf_tests` directory (if not present) and generate:

- `locustfile.py`
- `perf_<service>_test.py` (e.g. `perf_storage_test.py`)
- `requirements.txt`
- `README.md` (project README)

There are also legacy/compat commands available via the same CLI:

```bash
osdu_perf create-service <name> --output-dir ./services
osdu_perf create-locustfile --output ./locustfile.py
```

### Run a Locust test

From inside the generated `perf_tests/` (or your project folder):

```bash
locust -f locustfile.py --host https://your-api-host --partition your-partition --appid your-app-id
```

Additional Locust options are supported (e.g. `-u`, `-r`, `--headless`, `-t`).

## 📚 Key Concepts and Components

- `PerformanceUser` (in `osdu_perf.locust.user_base`)
  - Inherits from Locust's `HttpUser`.
  - On start, it initializes `InputHandler` and `ServiceOrchestrator` and discovers registered tests.
  - Implements a task that calls each discovered service's `execute()` method.

- `BaseService` (in `osdu_perf.core.base_service`)
  - Abstract base class for service test classes.
  - Convention: implement `execute(headers=None, partition=None, base_url=None)` (this matches the project templates and the locust user flow).

- `ServiceOrchestrator` (in `osdu_perf.core.service_orchestrator`)
  - Auto-discovers test classes defined in files matching `perf_*_test.py` in the current working directory and instantiates them with the HTTP client.
  - Also provides a legacy helper `register_service_sample()` to load service modules from a `services/` folder.

- `InputHandler` (in `osdu_perf.core.input_handler`)
  - Reads Locust `environment` values (host, parsed command-line options like `--partition` and `--appid`) and prepares request headers.
  - Uses `AzureTokenManager` to obtain an access token and adds it to the headers.

- `AzureTokenManager` (in `osdu_perf.core.auth`)
  - Wrapper around Azure credential providers (Azure CLI, Managed Identity, DefaultAzureCredential).
  - Use `get_access_token(scope)` to obtain a bearer token for requests.

## 🧩 Project layout (scaffolded)

```
perf_tests/
├── locustfile.py            # Main Locust file created by the CLI
├── perf_<service>_test.py   # Example: perf_storage_test.py
├── requirements.txt
└── README.md
```

The package also includes templates (see `osdu_perf/templates`) for `locustfile` and service files.

## 🛠️ Writing Tests

- File naming: follow the `perf_*_test.py` pattern to allow automatic discovery by `ServiceOrchestrator`.
- Class naming: create classes that inherit from `BaseService` (templates use `PerformanceTest` suffix but discovery is driven by subclassing `BaseService`).
- Implement `execute(headers=None, partition=None, base_url=None)` to perform service calls using `self.client` (the HTTP client provided by Locust).

Example snippet (simplified):

```python
from osdu_perf import BaseService

class StoragePerformanceTest(BaseService):
    def __init__(self, client=None):
        super().__init__(client)
        self.name = "storage"

    def execute(self, headers=None, partition=None, base_url=None):
        resp = self.client.get(f"{base_url}/api/storage/v1/health", headers=headers, name="storage_health")
        print(resp.status_code)
```

## 🧪 Development

- Run unit tests:

```bash
pytest
```

- Formatting and linting (if dev extras installed):

```bash
black osdu_perf/
flake8 osdu_perf/
```

## 📄 License

This project is licensed under the MIT License — see the `LICENSE` file for details.

## 🆘 Contact

For questions: janrajcj@microsoft.com

---

Generated from the repository code (synced with `osdu_perf` package).

