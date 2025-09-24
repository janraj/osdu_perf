# 🔥 OSDU Performance Testing Framework

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/osdu-perf.svg)](https://test.pypi.org/project/osdu-perf/)

A comprehensive Python framework for performance testing OSDU (Open Subsurface Data Universe) services. Features automatic test discovery, Azure authentication, Locust integration, and both local and cloud-based load testing capabilities.

## 📋 Key Features

✅ **Automatic Test Discovery** - Auto-discovers `perf_*_test.py` files  
✅ **Azure Authentication** - Seamless Azure AD token management  
✅ **Locust Integration** - Built on industry-standard Locust framework  
✅ **Local & Cloud Testing** - Run tests locally or on Azure Load Testing  
✅ **CLI Tools** - Comprehensive command-line interface  
✅ **Template System** - Pre-built templates for common OSDU services  
✅ **No File Generation** - Clean workflow with bundled templates  
✅ **Service-Specific Naming** - Smart naming based on detected services  

## 🚀 Quick Start

### Installation

```bash
# Install from TestPyPI
pip install -i https://test.pypi.org/simple/ osdu-perf
```

### 1. Initialize a New Project

```bash
# Create a performance testing project for storage service
osdu_perf init storage

# This creates a perf_tests/ directory with:
# - perf_storage_test.py (test implementation)
# - requirements.txt (dependencies)
# - README.md (project documentation)
# - azureloadtest.py (Azure Load Testing script)
```

### 2. Run Local Performance Tests

```bash
# Basic local test (uses bundled locustfile template)
osdu_perf run local \
  --host https://your-osdu-host.com \
  --partition your-partition-id \
  --token "your-bearer-token" \
  --users 10 --run-time 60s

# With web UI for monitoring
osdu_perf run local \
  --host https://your-osdu-host.com \
  --partition your-partition-id \
  --token "your-bearer-token" \
  --web-ui
```

### 3. Run Azure Load Tests

```bash
# Run performance tests on Azure Load Testing service
osdu_perf run azure_load_test \
  --subscription-id "your-azure-subscription-id" \
  --resource-group "your-resource-group" \
  --location "eastus" \
  --partition "your-partition-id" \
  --token "your-bearer-token" \
  --app-id "your-azure-ad-app-id"
```

## 🛠️ Command Reference

### 📊 Run Commands

#### Local Performance Testing

```bash
osdu_perf run local [OPTIONS]
```

**Required Parameters:**
- `--host`: OSDU host URL (e.g., https://your-osdu-host.com)
- `--partition`: OSDU data partition ID (e.g., opendes)  
- `--token`: Bearer token for OSDU authentication

**Optional Parameters:**
- `--users` (`-u`): Number of concurrent users (default: 10)
- `--spawn-rate` (`-r`): User spawn rate per second (default: 2)
- `--run-time` (`-t`): Test duration (default: 60s)
- `--locustfile` (`-f`): Custom locustfile to use
- `--web-ui`: Run with web UI (opens http://localhost:8089)
- `--headless`: Run in headless mode (default)
- `--verbose` (`-v`): Enable verbose output
- `--list-locustfiles`: List available bundled locustfiles

**Examples:**
```bash
# Basic headless test
osdu_perf run local --host https://api.example.com --partition opendes --token "abc123"

# Web UI with custom settings
osdu_perf run local --host https://api.example.com --partition opendes --token "abc123" --web-ui --users 50 --spawn-rate 5

# Extended test duration
osdu_perf run local --host https://api.example.com --partition opendes --token "abc123" --run-time 10m --users 25
```

#### Azure Load Testing

```bash
osdu_perf run azure_load_test [OPTIONS]
```

**Required Parameters:**
- `--subscription-id`: Azure subscription ID
- `--resource-group`: Azure resource group name
- `--location`: Azure region (e.g., eastus, westus2)
- `--partition`: OSDU data partition ID
- `--token`: Bearer token for OSDU authentication  
- `--app-id`: Azure AD Application ID

**Optional Parameters:**
- `--loadtest-name`: Azure Load Testing resource name (auto-generated)
- `--test-name`: Test name (auto-generated with timestamp)
- `--engine-instances`: Number of load generator instances (default: 1)
- `--users` (`-u`): Number of concurrent users (default: 10)
- `--spawn-rate` (`-r`): User spawn rate per second (default: 2)
- `--run-time` (`-t`): Test duration (default: 60s)
- `--directory` (`-d`): Directory containing test files (default: current)
- `--force`: Force overwrite existing tests
- `--verbose` (`-v`): Enable verbose output

**Examples:**
```bash
# Basic Azure Load Test
osdu_perf run azure_load_test \
  --subscription-id "12345678-1234-1234-1234-123456789012" \
  --resource-group "myResourceGroup" \
  --location "eastus" \
  --partition "opendes" \
  --token "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9..." \
  --app-id "87654321-4321-4321-4321-210987654321"

# High-scale cloud test
osdu_perf run azure_load_test \
  --subscription-id "12345678-1234-1234-1234-123456789012" \
  --resource-group "myResourceGroup" \
  --location "eastus" \
  --partition "opendes" \
  --token "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9..." \
  --app-id "87654321-4321-4321-4321-210987654321" \
  --users 100 --engine-instances 5 --run-time 30m
```

### 🛠️ Project Management Commands

#### Initialize New Project

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

#### Create Standalone Locustfile

```bash
osdu_perf locustfile [OPTIONS]
```

**Parameters:**
- `--output` (`-o`): Output file path (default: locustfile.py)

#### Version Information

```bash
osdu_perf version                   # Show version information
```

## 🏗️ How It Works

### 🔍 Automatic Service Discovery

The framework automatically detects services from your `perf_*_test.py` files:

```
perf_tests/
├── perf_storage_test.py     → Detects "storage" service
├── perf_search_test.py      → Detects "search" service  
├── perf_wellbore_test.py    → Detects "wellbore" service
```

### 🎯 Smart Resource Naming

Based on detected services, resources are automatically named:
- **Load Test Resource**: `osdu-{service}-loadtest` (e.g., `osdu-storage-loadtest`)
- **Test Name**: `osdu_{service}_test_{timestamp}` (e.g., `osdu_storage_test_20250924_152250`)

### 📦 Bundled Templates

No more file generation clutter! The framework uses bundled templates:
- **Local Tests**: Creates temporary locustfile from bundled template
- **Azure Tests**: Packages test files with temporary locustfile if needed
- **Clean Workflow**: No leftover generated files in your workspace

### 🔐 Authentication Flows

**Local Testing:**
- Uses environment variables: `OSDU_HOST`, `OSDU_PARTITION`, `ADME_BEARER_TOKEN`
- Supports Azure CLI credentials and Managed Identity

**Azure Load Testing:**
- Environment variables: `OSDU_PARTITION`, `ADME_BEARER_TOKEN`, `APPID`
- Handles Azure authentication for resource management
- Passes OSDU credentials to load generator instances

## 📚 Framework Components

### Core Classes

#### `PerformanceUser` (Locust Integration)
- Base class for all performance testing users
- Inherits from Locust's `HttpUser`
- Auto-discovers and executes `perf_*_test.py` files
- Handles OSDU authentication and environment setup

#### `BaseService` (Test Base Class)
- Abstract base class for service test implementations  
- Convention: implement `execute(headers, partition, base_url)` method
- Automatic discovery by `ServiceOrchestrator`

#### `ServiceOrchestrator` (Test Discovery)
- Auto-discovers test classes in `perf_*_test.py` files
- Instantiates test classes with HTTP client
- Manages test execution lifecycle

#### `AzureTokenManager` (Authentication)
- Handles Azure AD authentication flows
- Supports Azure CLI, Managed Identity, and DefaultAzureCredential
- Provides bearer tokens for OSDU API calls

## 🧪 Writing Performance Tests

### Test File Structure

Create test files following the `perf_*_test.py` naming pattern:

```python
# perf_storage_test.py
import os
from osdu_perf import BaseService

class StoragePerformanceTest(BaseService):
    """
    Performance test class for Storage Service
    
    This class will be automatically discovered and executed.
    """
    
    def __init__(self, client=None):
        super().__init__(client)
        self.name = "storage"
    
    def execute(self, headers=None, partition=None, base_url=None):
        """
        Execute storage performance tests
        
        Args:
            headers: HTTP headers including authentication
            partition: Data partition ID  
            base_url: Base URL for the service
        """
        print(f"🔥 Executing {self.name} performance tests...")
        
        # Test 1: Health check
        try:
            response = self.client.get(
                f"{base_url}/api/storage/v2/info",
                headers=headers,
                name="storage_health_check"
            )
            print(f"Health check status: {response.status_code}")
        except Exception as e:
            print(f"❌ Health check failed: {e}")
        
        # Test 2: Create record
        try:
            test_data = {
                "kind": f"osdu:wks:{partition}:storage:1.0.0",
                "data": {"test": "data"}
            }
            
            response = self.client.post(
                f"{base_url}/api/storage/v2/records",
                json=test_data,
                headers=headers,
                name="storage_create_record"
            )
            print(f"Create record status: {response.status_code}")
        except Exception as e:
            print(f"❌ Create record failed: {e}")
        
        print(f"✅ Completed {self.name} performance tests")
    
    def provide_explicit_token(self) -> str:
        """Provide explicit bearer token from environment"""
        return os.environ.get('ADME_BEARER_TOKEN', '')
```

### Key Points

1. **File Naming**: Must follow `perf_*_test.py` pattern
2. **Class Naming**: Must end with `PerformanceTest` and inherit from `BaseService`
3. **execute() Method**: Entry point for all test scenarios
4. **HTTP Client**: Use `self.client` for requests (pre-configured with Locust)
5. **Request Naming**: Use `name` parameter for Locust statistics grouping

### HTTP Request Examples

```python
# GET request
response = self.client.get(
    f"{base_url}/api/storage/v2/records/{record_id}",
    headers=headers,
    name="storage_get_record"
)

# POST request with JSON
response = self.client.post(
    f"{base_url}/api/storage/v2/records",
    json=payload,
    headers=headers, 
    name="storage_create_record"
)

# PUT request
response = self.client.put(
    f"{base_url}/api/storage/v2/records/{record_id}",
    json=updated_payload,
    headers=headers,
    name="storage_update_record"
)

# DELETE request
response = self.client.delete(
    f"{base_url}/api/storage/v2/records/{record_id}",
    headers=headers,
    name="storage_delete_record"
)
```

## 🔧 Configuration & Environment Variables

### Local Testing Environment Variables
- `OSDU_HOST`: Base URL of OSDU instance
- `OSDU_PARTITION`: Data partition ID
- `ADME_BEARER_TOKEN`: Authentication token

### Azure Load Testing Environment Variables
- `OSDU_PARTITION`: Data partition ID
- `ADME_BEARER_TOKEN`: Authentication token
- `APPID`: Azure AD Application ID

### Azure Authentication
The framework supports multiple Azure authentication methods:
- **Azure CLI**: `az login` credentials
- **Managed Identity**: For Azure-hosted environments
- **Service Principal**: Via environment variables

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
Test multiple services by creating multiple `perf_*_test.py` files:

```
perf_tests/
├── perf_storage_test.py    # Storage service tests
├── perf_search_test.py     # Search service tests
├── perf_schema_test.py     # Schema service tests
```

All will be automatically discovered and executed.

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
# Ensure test files follow naming pattern
ls perf_*_test.py

# Check class inheritance
grep "BaseService" perf_*_test.py
```

**Azure Load Testing Errors**
```bash
# Install Azure dependencies
pip install azure-cli azure-identity azure-mgmt-loadtesting azure-mgmt-resource requests
```

## 🧩 Project Structure (Generated)

```
perf_tests/
├── perf_<service>_test.py   # Service-specific test implementation
├── requirements.txt         # Python dependencies  
├── README.md               # Project documentation
└── azureloadtest.py        # Azure Load Testing script (legacy)
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

## 🚀 What's New in v1.0.16

- ✅ **New Azure Load Test Command**: `osdu_perf run azure_load_test`
- ✅ **Simplified Local Testing**: `osdu_perf run local` with bundled templates
- ✅ **No File Generation**: Clean workflow without generated files
- ✅ **Smart Service Detection**: Auto-detects services from `perf_*_test.py` files
- ✅ **Enhanced CLI**: Comprehensive command-line interface with validation
- ✅ **Improved Authentication**: Better Azure token management
- ✅ **Template System**: Modular template architecture

---

**Generated by OSDU Performance Testing Framework v1.0.16**

