# 🔥 OSDU Performance Testing Framework

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/osdu_perf.svg)](https://pypi.org/project/osdu_perf/)
[![PR Gate](https://github.com/janraj/osdu_perf/actions/workflows/pr-gate.yml/badge.svg)](https://github.com/janraj/osdu_perf/actions/workflows/pr-gate.yml)
[![Publish to PyPI](https://github.com/janraj/osdu_perf/actions/workflows/publish.yml/badge.svg)](https://github.com/janraj/osdu_perf/actions/workflows/publish.yml)
[![Coverage](https://codecov.io/gh/janraj/osdu_perf/branch/main/graph/badge.svg)](https://codecov.io/gh/janraj/osdu_perf)

A comprehensive Python framework for performance testing OSDU (Open Subsurface Data Universe) services. Features automatic test discovery, Azure authentication, Locust integration, and both local and cloud-based load testing capabilities with intelligent service orchestration.

## 📋 Key Features

✅ **Service Orchestration** - Intelligent service discovery and execution management  
✅ **Azure Authentication** - Seamless Azure AD token management with multiple credential flows  
✅ **Dual Execution Modes** - Run locally with Locust or scale with Azure Load Testing  
✅ **CLI Tools** - Comprehensive command-line interface with three main commands  
✅ **Template System** - Pre-built templates for common OSDU services  
✅ **Configuration Management** - YAML-based configuration with environment-aware settings  
✅ **Metrics Collection** - Schema-driven telemetry to Azure Data Explorer (Kusto) with V3 tables  
✅ **Environment Detection** - Automatically adapts behavior for local vs Azure environments  

## 🏗️ Framework Architecture

### Core Components
- **`PerformanceUser`**: Locust integration with automatic service discovery
- **`ServiceOrchestrator`**: Plugin architecture for test discovery and execution
- **`BaseService`**: Abstract base class for implementing performance tests
- **`InputHandler`**: Configuration management with split config (system + test) and environment detection
- **`AzureTokenManager`**: Multi-credential authentication system
- **`TelemetryDispatcher`**: Builds test reports from Locust stats and fans out to enabled telemetry plugins
- **`KustoPlugin`**: Schema-driven telemetry plugin — auto-creates V3 tables and ingests metrics to Azure Data Explorer

## 🚀 Quick Start

### Installation

```bash
# Install from PyPI
pip install osdu_perf
```

### Three Simple Commands

The framework provides three main commands for the complete performance testing workflow:

#### 1. Initialize Project (`init`)

```bash
# Create a new performance testing project
osdu_perf init <service_name>

# Examples:
osdu_perf init storage     # Creates storage service performance tests
osdu_perf init search      # Creates search service performance tests
osdu_perf init wellbore    # Creates wellbore service performance tests
```

**What this creates:**
```
perf_tests/
├── config/
│   ├── system_config.yaml    # OSDU/Azure environment + metrics configuration
│   └── test_config.yaml      # Scenario definitions and test defaults
├── locustfile.py             # Main test file with API calls
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

#### 2. Run Local Tests (`run local`)

```bash
# Run performance tests locally using Locust
osdu_perf run local --scenario health_check

```

**Features:**
- Uses Locust for load generation
- Azure CLI authentication for local development  
- Real-time web UI at http://localhost:8089
- Automatic service discovery and execution
- Automatic metric collection and sends to Kusto 

#### 3. Run Azure Load Tests (`run azure_load_test`)

```bash
# Deploy and run tests on Azure Load Testing service
osdu_perf run azure_load_test --scenario health_check
```

**Features:**
- Creates Azure Load Testing resources automatically
- Scales to hundreds/thousands of concurrent users
- Managed Identity authentication in Azure
- Comprehensive metrics and reporting
- Entitlement will be created on ADME for azure load tests 

## 🛠️ Command Reference

### 1. Initialize Command

```bash
osdu_perf init <service_name> [OPTIONS]
```

**Parameters:**
- `service_name`: Name of the OSDU service to test (e.g., storage, search, wellbore)
- `--force`: Force overwrite existing files without prompting

**Examples:**
```bash
osdu_perf init storage              # Initialize storage service tests
osdu_perf init search --force       # Force overwrite existing search tests
osdu_perf init wellbore            # Initialize wellbore service tests
```

**Generated Files:**
- `config/system_config.yaml` - OSDU/Azure environment and metrics settings
- `config/test_config.yaml` - Scenario definitions and test defaults
- `locustfile.py` - Main test file with API calls to your service
- `requirements.txt` - Python dependencies
- `README.md` - Project-specific documentation

### 2. Local Testing Command

```bash
osdu_perf run local [OPTIONS]
```

**Configuration:**
- Uses config files in `config/`
- CLI arguments override config file settings
- Environment variables provide runtime values

**Key Options:**
- `--scenario`: Single scenario key from `config/test_config.yaml` (required)
- `--host`: OSDU host URL (overrides config)
- `--partition`: OSDU data partition ID (overrides config)  
- `--app-id`: Azure AD Application ID (overrides config)
- `--users` (`-u`): Number of concurrent users (default: from config)
- `--spawn-rate` (`-r`): User spawn rate per second (default: from config)
- `--run-time` (`-t`): Test duration (default: from config)

**Examples:**
```bash
# Basic run
osdu_perf run local --scenario health_check

# Override specific settings
osdu_perf run local --scenario health_check --users 50 --run-time 5m

# Full override
osdu_perf run local \
  --scenario health_check \
  --host https://api.example.com \
  --partition dp1 \
  --app-id 12345678-1234-1234-1234-123456789abc \
  --users 25 --spawn-rate 5
```

### 3. Azure Load Testing Command

```bash
osdu_perf run azure_load_test [OPTIONS]
```

**Required Parameters:**
- `--scenario`: Single scenario key from `config/test_config.yaml`


**Optional Parameters:**
- `--loadtest-name`: Azure Load Testing resource name (auto-generated)
- `--test-name`: Test name (auto-generated with timestamp)
- `--engine-instances`: Number of load generator instances (default: from config)
- `--users` (`-u`): Number of concurrent users per instance (default: from config)
- `--run-time` (`-t`): Test duration (default: from config)

**Examples:**
```bash
# Basic Azure Load Test
osdu_perf run azure_load_test \
  --scenario health_check \
  --subscription-id "12345678-1234-1234-1234-123456789012" \
  --resource-group "myResourceGroup" \
  --location "eastus"

# High-scale cloud test
osdu_perf run azure_load_test \
  --scenario health_check \
  --subscription-id "12345678-1234-1234-1234-123456789012" \
  --resource-group "myResourceGroup" \
  --location "eastus" \
  --users 100 --engine-instances 5 --run-time 30m
```

## 📝 Configuration System

### Config Structure

The framework uses system and tests configuration files that support both local and Azure environments:

**`config/system_config.yaml`** — shared environment and metrics settings:

```yaml
# OSDU Environment Configuration
osdu_environment:
  host: "https://your-osdu-host.com"
  partition: "your-partition-id"
  app_id: "your-azure-app-id"

  performance_tier: "Standard"     # e.g. Standard, Flex, Developer
  version: "25.2.35"

# Metrics Collection Configuration (optional)
# Only 'cluster' is required — database defaults to 'adme-performance-db',
# ingest_uri is auto-derived, auth is auto-detected.
metrics_collector:
  kusto:
    cluster: "https://your-kusto-cluster.eastus.kusto.windows.net"
    database: "your-database"              # optional — defaults to "adme-performance-db"

# Azure Load Test resource location
test_environment:
  subscription_id: "your-azure-subscription-id"
  resource_group: "your-resource-group"
  location: "eastus"
```

**`config/test_config.yaml`** — performance-tier profiles and scenario definitions:

```yaml
performance_tier_profiles:
  standard:
    default_wait_time:
      min: 1
      max: 3
    users: 10
    spawn_rate: 2
    run_time: "60s"
    engine_instances: 1

scenarios:
  health_check:
    test_name_prefix: "health_check_test"
    test_run_id_description: "Health check scenario"
```

### Configuration Hierarchy

The framework uses a layered configuration approach:

1. **`config/system_config.yaml`** — environment, metrics, and Azure resource settings
2. **`config/test_config.yaml`** — performance-tier profiles and per-scenario overrides
3. **CLI arguments** (highest priority, including required `--scenario`)


## 🏗️ How It Works

### 🔍 Simple API-Based Approach

The framework now uses a simplified API-based approach where developers write test methods directly in `locustfile.py`:

```
perf_tests/
├── locustfile.py            → OSDUUser class with @task methods for testing
├── config/system_config.yaml → Host, partition, authentication, Azure settings
├── config/test_config.yaml   → Scenario definitions and test defaults
├── requirements.txt         → Dependencies (osdu_perf package)
```

**Simplified Process:**
1. `osdu_perf init <service>` generates `locustfile.py` template
2. Developers add `@task` methods with API calls (`self.get()`, `self.post()`, etc.)
3. `PerformanceUser` base class handles authentication, headers, tokens automatically
4. Run with `osdu_perf run local` or `osdu_perf run azure_load_test`


### 🎯 Smart Resource Naming

Based on detected services, Azure resources are automatically named:
- **Load Test Resource**: `osdu-{service}-loadtest-{timestamp}`
- **Test Name**: `osdu_{service}_test_{timestamp}`
- **Example**: `osdu-storage-loadtest-20241028` with test `osdu_storage_test_20241028_142250`

### 🔐 Multi-Environment Authentication

**Local Development:**
- Azure CLI credentials (`az login`)
- Manual token via config or environment variables
- Automatic token refresh and caching

**Azure Load Testing:**
- Managed Identity authentication (no secrets needed)
- Environment variables injected by Azure Load Testing service
- Automatic credential detection and fallback

### 📊 Telemetry & Metrics Collection

**Schema-Driven Kusto Integration:**
- Schema definitions are the single source of truth — table DDL, CSV headers, and row builders are all derived automatically
- Detects environment (local vs Azure) and uses appropriate auth (Azure CLI locally, Managed Identity in Azure)
- `ingest_uri` is auto-derived from `cluster` — no manual configuration needed
- `database` defaults to `"adme-performance-db"` if not set
- Tables are auto-created via `.create-merge table` on first publish
- Pushes detailed metrics to three V3 tables:
  - `LocustMetricsV3` — Per-endpoint request statistics and percentiles
  - `LocustExceptionsV3` — Error and exception tracking
  - `LocustTestSummaryV3` — Aggregated test run summaries

## 🧪 Writing Performance Tests

### Simple API-Based Approach

The framework generate your `locustfile.py`:

```python
"""
OSDU Performance Tests - Locust Configuration
Generated by OSDU Performance Testing Framework
"""

import os
from locust import events, task, tag
from osdu_perf import PerformanceUser

# STEP 1: Register custom CLI args with Locust
@events.init_command_line_parser.add_listener
def add_custom_args(parser):
    """Add OSDU-specific command line arguments"""
    parser.add_argument("--partition", type=str, default=os.getenv("PARTITION"), help="OSDU Data Partition ID")
    parser.add_argument("--appid", type=str, default=os.getenv("APPID"), help="Azure AD Application ID")

class OSDUUser(PerformanceUser):
    """
    OSDU Performance Test User
    
    This class automatically:
    - Handles Azure authentication using --appid
    - Manages HTTP headers and tokens
    - Provides simple API methods for testing
    - Manages Locust user simulation and load testing
    """
    
    def on_start(self):
        """Called when a user starts - performs setup"""
        super().on_start()
        
        # Access OSDU parameters from Locust parsed options or environment variables
        partition = getattr(self.environment.parsed_options, 'partition', None) or os.getenv('PARTITION')
        host = getattr(self.environment.parsed_options, 'host', None) or self.host or os.getenv('HOST')
        token = os.getenv('ADME_BEARER_TOKEN')  # Token only from environment for security
        appid = getattr(self.environment.parsed_options, 'appid', None) or os.getenv('APPID')
        
        print(f"� Started performance testing user")
        print(f"   📍 Partition: {partition}")
        print(f"   🌐 Host: {host}")
        print(f"   🔑 Token: {'***' if token else 'Not provided'}")
        print(f"   🆔 App ID: {appid or 'Not provided'}")
    
    @tag("storage", "health_check")
    @task(1)
    def check_service_health(self):
        # Simple API call - framework handles headers, tokens, authentication
        self.get("/api/storage/v2/health")
    
    @tag("storage", "health_check")
    @task(2)
    def test_service_endpoints(self):
        # More API calls for your service
        self.get("/api/storage/v2/info")
        self.post("/api/storage/v2/records", json={"test": "data"})
```

### Key Implementation Points

1. **Inherit from PerformanceUser**: Your class extends `PerformanceUser` which handles all authentication and setup
2. **Use @task decorators**: Mark methods with `@task(weight)` to define test scenarios
3. **Simple HTTP methods**: Use `self.get()`, `self.post()`, `self.put()`, `self.delete()` - framework handles headers/tokens
4. **No manual authentication**: Framework automatically handles Azure AD tokens and HTTP headers
5. **Environment awareness**: Automatically adapts for local vs Azure Load Testing environments

### Available HTTP Methods

The `PerformanceUser` base class provides these simple methods:

```python
# GET request
self.get("/api/storage/v2/records/12345")

# POST request with JSON data
self.post("/api/storage/v2/records", json={
    "kind": "osdu:wks:partition:storage:1.0.0",
    "data": {"test": "data"}
})

# PUT request
self.put("/api/storage/v2/records/12345", json=updated_data)

# DELETE request  
self.delete("/api/storage/v2/records/12345")

# Custom headers (if needed)
self.get("/api/storage/v2/info", headers={"Custom-Header": "value"})

# Also locust client available 

self.client.get("/api/storage/v2/records/12345")
```

### Authentication Handling

The framework automatically manages authentication:

- **Local Development**: Uses Azure CLI credentials (`az login`)
- **Azure Load Testing**: Uses Managed Identity  
- **Manual Override**: Set `ADME_BEARER_TOKEN` environment variable
- **All requests**: Automatically include proper Authorization headers

## 🔧 Configuration & Environment Variables

### Configuration Hierarchy

The framework uses a layered configuration approach (highest priority first):

1. **CLI arguments** - Direct command-line overrides
2. **Environment variables** - Runtime values  
3. **config/system_config.yaml + config/test_config.yaml** - Project-specific settings
4. **Default values** - Framework defaults

### Environment Variables

**Universal Variables:**
- `OSDU_HOST`: Base URL of OSDU instance
- `OSDU_PARTITION`: Data partition ID
- `OSDU_APP_ID`: Azure AD Application ID
- `ADME_BEARER_TOKEN`: Manual bearer token override

**Azure Load Testing Variables (auto-set):**
- `AZURE_LOAD_TEST=true`: Indicates Azure environment
- `PARTITION`: Data partition ID
- `LOCUST_HOST`: OSDU host URL
- `APPID`: Azure AD Application ID

**Metrics Collection:**
- `KUSTO_CLUSTER`: Azure Data Explorer cluster URL
- `KUSTO_DATABASE`: Database name for metrics
- `TEST_RUN_ID`: Unique identifier for test run

### Azure Authentication

The framework supports multiple Azure authentication methods with automatic detection:

**Local Development:**
- Azure CLI credentials (`az login`)
- Service Principal (via environment variables)
- DefaultAzureCredential chain

**Azure Environments:**
- Managed Identity (preferred for Azure-hosted resources)
- System-assigned or user-assigned identities
- Automatic credential detection and fallback

## 📊 Monitoring & Results

### Local Testing (Web UI)
- Open http://localhost:8089 after starting with `--web-ui`
- Real-time performance metrics
- Request statistics and response times
- Download results as CSV

### Azure Load Testing
- Monitor in Azure Portal under "Load Testing"
- Comprehensive dashboards and metrics
- Automated result retention
- Integration with Azure Monitor

### Key Metrics
- **Requests per second (RPS)**
- **Average response time**
- **95th percentile response time**  
- **Error rate**
- **Failure count by endpoint**

## 🚀 Advanced Usage


### Multiple Services
Test multiple services by adding more `@task` methods in your `locustfile.py`:

```python
class OSDUUser(PerformanceUser):
    
    @task(3)  # Higher weight = more frequent execution
    def test_storage_apis(self):
        self.get("/api/storage/v2/info")
        self.post("/api/storage/v2/records", json={"data": "test"})
    
    @task(2) 
    def test_search_apis(self):
        self.get("/api/search/v2/query")
        self.post("/api/search/v2/query", json={"query": "*"})
    
    @task(1)
    def test_schema_apis(self):
        self.get("/api/schema-service/v1/schema")
```

All tests run in the same `locustfile.py` with automatic load balancing based on task weights.

### CI/CD Integration

```yaml
# Example GitHub Actions workflow
- name: Run OSDU Performance Tests
  run: |
    osdu_perf run local \
      --host ${{ secrets.OSDU_HOST }} \
      --partition ${{ secrets.OSDU_PARTITION }} \
      --token ${{ secrets.OSDU_TOKEN }} \
      --headless \
      --users 5 \
      --run-time 2m
```

## 🐛 Troubleshooting

### Common Issues

**Authentication Errors**
```bash
# Ensure Azure CLI is logged in
az login

```

**Import Errors**
```bash
# Install dependencies
pip install -r requirements.txt
```

**Service Discovery Issues**
```bash
# Ensure locustfile.py exists and inherits from PerformanceUser
ls locustfile.py

# Check class inheritance
grep "PerformanceUser" locustfile.py
```

**Azure Load Testing Errors**
```bash
# Install Azure dependencies
pip install azure-cli azure-identity azure-mgmt-loadtesting azure-mgmt-resource requests
```

## 🧩 Project Structure (Generated)

```
perf_tests/
├── locustfile.py            # Main test file with API calls and @task methods
├── config/system_config.yaml # OSDU/Azure environment + metrics configuration
├── config/test_config.yaml   # Scenario definitions and test defaults
├── requirements.txt         # Python dependencies (osdu_perf package)  
└── README.md               # Project documentation
```

## 🧪 Development

### Running Tests
```bash
pytest tests/
```

### Code Quality
```bash
# Formatting
black osdu_perf/

# Linting  
flake8 osdu_perf/
```

### Building Package
```bash
# Build wheel and source distribution
python -m build

# Upload to TestPyPI
python -m twine upload --repository testpypi dist/*
```

## 📄 License

This project is licensed under the MIT License — see the `LICENSE` file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/janraj/osdu_perf/issues)
- **Contact**: janrajcj@microsoft.com
- **Documentation**: This README and inline code documentation

---

**Generated by OSDU Performance Testing Framework v1.0.42**

