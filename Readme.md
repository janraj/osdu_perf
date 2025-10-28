# 🔥 OSDU Performance Testing Framework

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/osdu-perf.svg)](https://pypi.org/project/osdu-perf/)

A comprehensive Python framework for performance testing OSDU (Open Subsurface Data Universe) services. Features automatic test discovery, Azure authentication, Locust integration, and both local and cloud-based load testing capabilities with intelligent service orchestration.

## 📋 Key Features

✅ **Service Orchestration** - Intelligent service discovery and execution management  
✅ **Azure Authentication** - Seamless Azure AD token management with multiple credential flows  
✅ **Dual Execution Modes** - Run locally with Locust or scale with Azure Load Testing  
✅ **CLI Tools** - Comprehensive command-line interface with three main commands  
✅ **Template System** - Pre-built templates for common OSDU services  
✅ **Configuration Management** - YAML-based configuration with environment-aware settings  
✅ **Metrics Collection** - Automated metrics push to Azure Data Explorer (Kusto)  
✅ **Environment Detection** - Automatically adapts behavior for local vs Azure environments  

## 🏗️ Framework Architecture

### Core Components
- **`PerformanceUser`**: Locust integration with automatic service discovery
- **`ServiceOrchestrator`**: Plugin architecture for test discovery and execution
- **`BaseService`**: Abstract base class for implementing performance tests
- **`InputHandler`**: Configuration management and environment detection
- **`AzureTokenManager`**: Multi-credential authentication system  

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
├── config.yaml               # Framework configuration
├── locustfile.py             # Main test file with API calls
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

#### 2. Run Local Tests (`run local`)

```bash
# Run performance tests locally using Locust
osdu_perf run local --config config.yaml

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
osdu_perf run azure_load_test --config config.yaml 
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
- `config.yaml` - Framework configuration with OSDU connection details
- `locustfile.py` - Main test file with API calls to your service
- `requirements.txt` - Python dependencies
- `README.md` - Project-specific documentation

### 2. Local Testing Command

```bash
osdu_perf run local [OPTIONS]
```

**Configuration:**
- Uses `config.yaml` for base configuration
- CLI arguments override config file settings
- Environment variables provide runtime values

**Key Options:**
- `--config`: Path to config.yaml file (required)
- `--host`: OSDU host URL (overrides config)
- `--partition`: OSDU data partition ID (overrides config)  
- `--app-id`: Azure AD Application ID (overrides config)
- `--users` (`-u`): Number of concurrent users (default: from config)
- `--spawn-rate` (`-r`): User spawn rate per second (default: from config)
- `--run-time` (`-t`): Test duration (default: from config)

**Examples:**
```bash
# Basic run using config.yaml
osdu_perf run local --config config.yaml

# Override specific settings
osdu_perf run local --config config.yaml --users 50 --run-time 5m

# Full override
osdu_perf run local \
  --config config.yaml \
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
- `--config`: Path to config.yaml file


**Optional Parameters:**
- `--loadtest-name`: Azure Load Testing resource name (auto-generated)
- `--test-name`: Test name (auto-generated with timestamp)
- `--engine-instances`: Number of load generator instances (default: from config)
- `--users` (`-u`): Number of concurrent users per instance (default: from config)
- `--run-time` (`-t`): Test duration (default: from config)

**Examples:**
```bash
# Basic Azure Load Test using config
osdu_perf run azure \
  --config config.yaml \
  --subscription-id "12345678-1234-1234-1234-123456789012" \
  --resource-group "myResourceGroup" \
  --location "eastus"

# High-scale cloud test
osdu_perf run azure \
  --config config.yaml \
  --subscription-id "12345678-1234-1234-1234-123456789012" \
  --resource-group "myResourceGroup" \
  --location "eastus" \
  --users 100 --engine-instances 5 --run-time 30m
```

## 📝 Configuration System

### config.yaml Structure

The framework uses a centralized configuration file that supports both local and Azure environments:

```yaml
# OSDU Environment Configuration
osdu_environment:
  # OSDU instance details (required for run local command)
  host: "https://your-osdu-host.com"
  partition: "your-partition-id"
  app_id: "your-azure-app-id"
  
  # OSDU deployment details (optional - used for metrics collection)
  sku: "Standard"
  version: "25.2.35"
  
  # Authentication (optional - uses automatic token generation if not provided)
  auth:
    # Manual token override (optional)
    token: ""

# Metrics Collection Configuration  
metrics_collector:
  # Kusto (Azure Data Explorer) Configuration
  kusto:
    cluster: "https://your-kusto-cluster.eastus.kusto.windows.net"
    database: "your-database"
    ingest_uri: "https://ingest-your-kusto.eastus.kusto.windows.net"

# Test Configuration (Optional)
test_settings:
  # Azure Load Test resource and test locations
  subscription_id: "your-azure-subscription-id"
  resource_group: "your-resource-group"
  location: "eastus"
  
  # Test-specific configurations
  default_wait_time: 
    min: 1
    max: 3
  users: 10
  spawn_rate: 2
  run_time: "60s"
  engine_instances: 1
  test_name_prefix: "osdu_perf_test"
  test_run_id_description: "Automated performance test"
```

### Configuration Hierarchy

The framework uses a layered configuration approach:

1. **config.yaml** (project-specific settings)
2. **CLI arguments** (highest priority)


## 🏗️ How It Works

### 🔍 Simple API-Based Approach

The framework now uses a simplified API-based approach where developers write test methods directly in `locustfile.py`:

```
perf_tests/
├── locustfile.py            → OSDUUser class with @task methods for testing
├── config.yaml              → Configuration for host, partition, authentication  
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

### 📊 Intelligent Metrics Collection

**Automatic Kusto Integration:**
- Detects environment (local vs Azure) automatically
- Uses appropriate authentication method
- Pushes detailed metrics to three tables:
  - `LocustMetrics` - Per-endpoint statistics
  - `LocustExceptions` - Error tracking
  - `LocustTestSummary` - Overall test summaries

## 🧪 Writing Performance Tests

### Simple API-Based Approach

The framework now uses a simple API-based approach where you make HTTP calls directly in your `locustfile.py`:

```python
"""
OSDU Performance Tests - Locust Configuration
Generated by OSDU Performance Testing Framework
"""

import os
from locust import events, task
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
    
    @task(1)
    def check_service_health(self):
        # Simple API call - framework handles headers, tokens, authentication
        self.get("/api/storage/v2/health")
    
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
3. **config.yaml** - Project-specific settings
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

### Custom Locustfile
If you need custom behavior, provide your own locustfile:

```bash
osdu_perf run local \
  --host https://api.example.com \
  --partition opendes \
  --token "abc123" \
  --locustfile my_custom_locustfile.py
```

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

# Or verify environment variables are set
echo $ADME_BEARER_TOKEN
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
├── config.yaml              # Framework configuration (OSDU, metrics, test settings)
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

## 🚀 What's New in v1.0.24

- ✅ **Three-Command Workflow**: `init`, `run local`, `run azure` - complete testing pipeline
- ✅ **Configuration-Driven**: YAML-based configuration with environment-aware settings
- ✅ **Service Orchestration**: Intelligent service discovery with lifecycle management
- ✅ **Enhanced Authentication**: Multi-credential Azure authentication with automatic detection
- ✅ **Metrics Integration**: Automated Kusto metrics collection with environment detection
- ✅ **Template System**: Updated project templates with modern framework patterns
- ✅ **Error Handling**: Improved error handling and defensive coding patterns
- ✅ **CLI Improvements**: Better argument parsing and validation

---

**Generated by OSDU Performance Testing Framework v1.0.24**

