import os
from pathlib import Path
import getpass
from ...utils.logger import get_logger

class InitRunner:
    def __init__(self):
        self.initialized = False
        self.logger = get_logger('init_runner')

    def initialize(self):
        if not self.initialized:
            # Perform initialization tasks here
            self.logger.info("Initializing...")
            self.initialized = True
        else:
            self.logger.info("Already initialized.")

    def create_project_config(self, output_path: Path, service_name: str = None) -> None:
        """Creates a config.yaml file for the project."""
        username = getpass.getuser()
        test_name_prefix = f"{username}_{service_name}" if service_name else f"{username}_osdu_test"
        
        

        # Best practice: Load this template from a file in a 'templates' directory
        config_content = f"""# OSDU Performance Testing Configuration
# This file contains configuration settings for the OSDU performance testing framework

# OSDU Environment Configuration [Must have]
osdu_environment:
  # OSDU instance details (required for run local and azure_load_test command)
  host: "https://your-osdu-host.com"
  partition: "your-partition-id"
  app_id: "your-azure-app-id"

  performance_tier: "Standard"
  version: "25.2.35"

# OSDU deployment details (optional - used for metrics collection)
# Metrics Collection Configuration  [Optional] 
# metrics_collector:
  # Kusto (Azure Data Explorer) Configuration
  # kusto:
  #  cluster: ""
  #  database: ""
  #  ingest_uri: ""

# Test Configuration (Must)
test_settings:
  # Where the azure load test resource and tests are located
  subscription_id: ""
  # resource_group: "adme-performance-rg"
  # location: "eastus"
  #Test specific configurations
  default_wait_time: 
    min: 1
    max: 3
  users: 10
  spawn_rate: 2
  run_time: "60s"
  engine_instances: 1
  test_name_prefix: "{test_name_prefix}"
  test_scenario: "{service_name}"
  test_run_id_description: "Test run for {service_name} api"
"""
        output_path.write_text(config_content, encoding='utf-8')
        self.logger.info(f"Created config.yaml at {output_path} generated prefix {test_name_prefix}")

    def create_requirements_file(self, output_path: Path):
        
        output_path.write_text(f"osdu_perf\n", encoding='utf-8')
        self.logger.info(f"Created {output_path.name}")

    def create_project_readme(self, output_path: Path, service_name: str):

        readme_content = f'''# {service_name.title()} Service Performance Tests

This project contains performance tests for the OSDU {service_name.title()} Service using the OSDU Performance Testing Framework v1.0.24.

## 📁 Project Structure

```
perf_tests/
├── config/
│   ├── system_config.yaml    # OSDU/Azure environment + metrics configuration
│   └── test_config.yaml      # Scenario definitions and test defaults
├── locustfile.py              # Main test file with API calls and @task methods
├── requirements.txt          # Python dependencies (osdu_perf package)
└── README.md                 # This file
```

## 🚀 Quick Start

### 1. Configure Your Environment
Edit config files in `config/`:
- `config/system_config.yaml`: OSDU environment details (host, partition, app_id), Azure settings, and metrics settings.
- `config/test_config.yaml`: scenario map and default test values.
- `--scenario` must be a single scenario key from `config/test_config.yaml`.

### 2. Customize Your Tests
Edit `locustfile.py` and add @task methods with:
- API endpoints for storage service
- Test scenarios using self.get(), self.post(), etc.
- Custom load patterns and user behavior
- could use all locust features inside the tests.
- could also use locust API for API calls. 

### 3. Run Performance Tests

#### Local Testing (Development)
```bash
# Basic run using split config files
osdu_perf run local --scenario record_size_1KB

# Override specific settings for testing
osdu_perf run local --scenario record_size_1KB --users 5 --run-time 30s

```

#### Azure Load Testing (Production Scale)
```bash
# Deploy and run on Azure Load Testing service
osdu_perf run azure_load_test --scenario record_size_1KB
  
```

## 📝 Writing Performance Tests
- Use the Locust documentation to write tests.
- ADME token, partition, app ID, and headers are passed to your tests.
- Headers contain a correlation ID by default. You can add more test-specific correlation IDs, but avoid removing the existing one as it helps collect metrics.
- Azure Load Test to ADME entitlement is created before running the tests.
- Metrics are collected at the end of the run and sent to the Kusto server.
- All new files must start with perf_*. These files will be uploaded to Azure Load Test to run.

### Simple API-Based Approach

Your main test file `locustfile.py` uses this simple pattern:

```python
import os
from locust import events, task
from osdu_perf import PerformanceUser

@events.init_command_line_parser.add_listener
def add_custom_args(parser):
    \"\"\"Add OSDU-specific command line arguments\"\"\"
    parser.add_argument("--partition", type=str, default=os.getenv("PARTITION"), help="OSDU Data Partition ID")
    parser.add_argument("--appid", type=str, default=os.getenv("APPID"), help="Azure AD Application ID")

class OSDUUser(PerformanceUser):
    \"\"\"
    OSDU Performance Test User
    
    This class automatically handles:
    - Azure authentication and token management
    - HTTP headers and request setup
    - Locust user simulation and load testing
    \"\"\"
    
    def on_start(self):
        \"\"\"Called when a user starts\"\"\"
        super().on_start()
        print(f"🚀 Started performance testing user")
    
    @task(3)  # Higher weight = more frequent execution
    def test_{service_name}_health(self):
        # Simple API call - framework handles headers, tokens automatically
        self.get("/api/{service_name}/v1/health")
    
    @task(2) 
    def test_{service_name}_info(self):
        self.get("/api/{service_name}/v1/info")
    
    @task(1)
    def test_{service_name}_operations(self):
        # POST request with JSON data
        self.post("/api/{service_name}/v1/records", json={{
            "kind": f"osdu:wks:{{partition}}:{service_name}:1.0.0",
            "data": {{"test": "data"}}
        }})
```


### Available HTTP Methods

```python
# GET request
self.get("/api/{service_name}/v1/records/12345")

# POST request with JSON data
self.post("/api/{service_name}/v1/records", json={{
    "kind": "osdu:wks:partition:{service_name}:1.0.0",
    "data": {{"test": "data"}}
}})

# PUT request
self.put("/api/{service_name}/v1/records/12345", json=updated_data)

# DELETE request  
self.delete("/api/{service_name}/v1/records/12345")

# Custom headers (if needed - auth headers added automatically)
self.get("/api/{service_name}/v1/info", headers={{"Custom-Header": "value"}})
```

## 🔧 Configuration

### Framework Configuration (split files)

The framework uses split configuration files:
- Can have own metrics collector 
- Can have multiple scenario definitions in `config/test_config.yaml` (run command accepts one scenario at a time)
- Can have own azure load test instance.

```yaml
# OSDU Environment Configuration
osdu_environment:
  host: "https://your-osdu-host.com"
  partition: "your-partition-id"
  app_id: "your-azure-app-id"
    performance_tier: "Standard"
  version: "25.2.35"

# Metrics Collection Configuration  
metrics_collector:
  kusto:
    cluster: "https://your-kusto-cluster.eastus.kusto.windows.net"
    database: "your-database"
    ingest_uri: "https://ingest-your-kusto.eastus.kusto.windows.net"

# Test Configuration
test_settings:
  subscription_id: "your-azure-subscription-id"
  resource_group: "your-resource-group"
  location: "eastus"
  default_wait_time: 
    min: 1
    max: 3
  users: 10
  spawn_rate: 2
  run_time: "60s"
  engine_instances: 1
```


### Authentication

The framework automatically handles Azure authentication:

**Local Development:**
- Azure CLI credentials (`az login`)
- Service Principal (environment variables)
- DefaultAzureCredential chain

**Azure Environments:**
- Managed Identity (preferred)
- Automatic credential detection and fallback

## 📊 Monitoring and Results

### Local Testing
- **Web UI**: Open http://localhost:8089 during test execution
- **Real-time metrics**: Request rates, response times, error rates
- **Results export**: Download CSV reports for analysis

### Azure Load Testing
- **Azure Portal**: Monitor in Azure Portal under "Load Testing"
- **Comprehensive dashboards**: Detailed performance metrics and trends
- **Automated retention**: Results stored automatically
- **Integration**: Works with Azure Monitor and Application Insights

### Key Metrics
- **Requests per second (RPS)**
- **Response time percentiles** (50th, 90th, 95th, 99th)
- **Error rate and failure counts**
- **Throughput and content transfer rates**

## 🐛 Troubleshooting

### Common Issues

1. **Authentication Errors**
   ```bash
   # Ensure Azure CLI is logged in for local testing
   az login
   
   # Or verify environment variables
   echo $ADME_BEARER_TOKEN
   ```

2. **Test File Issues**
   ```bash
   # Ensure locustfile.py exists and inherits from PerformanceUser
   ls locustfile.py
   
   # Check class inheritance
   grep "PerformanceUser" locustfile.py
   ```

3. **Configuration Issues**
   ```bash
    # Validate split config YAML files
    python -c "import yaml; yaml.safe_load(open('config/system_config.yaml')); yaml.safe_load(open('config/test_config.yaml'))"
   ```

4. **Missing Dependencies**
   ```bash
   # Install framework and dependencies
   pip install osdu_perf
   ```
5. **VPN required**
    ```bash
    VPN is required for sending metrics to Kusto when running the test locally. You can ignore connection-related errors in the script if you don’t need to send test metrics.
    ```
### Debugging Tips

- Use `--verbose` flag for detailed logging
- Check Azure CLI authentication: `az account show`
- Verify OSDU connectivity manually before running tests
- Start with small user counts (1-5) for initial testing

## 📚 Additional Resources

- [OSDU Performance Framework Documentation](https://github.com/janraj/osdu_perf)
- [Locust Documentation](https://docs.locust.io/)
- [Azure Load Testing](https://docs.microsoft.com/en-us/azure/load-testing/)
- [Azure Authentication](https://docs.microsoft.com/en-us/azure/developer/python/azure-sdk-authenticate)


**Generated by OSDU Performance Testing Framework v1.0.24**
'''
        
        output_path.write_text(readme_content, encoding='utf-8')
        self.logger.info(f"Created {output_path.name}")

    def create_locustfile_template(self, output_path: Path, service_name:str):
        service_list = service_name or ["example"]
        services_comment = f"# Simple API-based performance testing for {service_list[0]} service"

        template = f'''
"""
 *    Copyright (c) 2024. EPAM Systems, Inc
 *
 *    Licensed under the Apache License, Version 2.0 (the "License");
 *    you may not use this file except in compliance with the License.
 *    You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *    Unless required by applicable law or agreed to in writing, software
 *    distributed under the License is distributed on an "AS IS" BASIS,
 *    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *    See the License for the specific language governing permissions and
 *    limitations under the License.
 *
"""        
"""
OSDU Performance Tests - Locust Configuration
Generated by OSDU Performance Testing Framework

{services_comment}
"""

import os
from locust import HttpUser
from locust import events, task, tag
from osdu_perf import PerformanceUser


# STEP 1: Register custom CLI args with Locust
# Please dont remove this code as it is required for OSDU parameters.
@events.init_command_line_parser.add_listener
def add_custom_args(parser):
    """Add OSDU-specific command line arguments"""
    parser.add_argument("--partition", type=str, default=os.getenv("PARTITION"), help="OSDU Data Partition ID")
    # Note: --host is provided by Locust built-in, no need to add it here
    # Note: --token is not exposed as CLI arg for security, only via environment variable
    parser.add_argument("--appid", type=str, default=os.getenv("APPID"), help="Azure AD Application ID")


class OSDUUser(HttpUser):
    """
    OSDU Performance Test User
    
    This class automatically:
    - Handles Azure authentication and token management
    - Manages HTTP headers and request setup
    - Provides simple API methods (get, post, put, delete)
    - Manages Locust user simulation and load testing
    
    Usage:
        locust -f locustfile.py --host https://your-api.com --partition your-partition --appid your-app-id
    """
    
    # Optional: Customize user behavior
    # Default `wait_time` is provided by `PerformanceUser` (between(1, 3)).
    # To override in the generated file, uncomment and import `between` from locust:
    # from locust import between
    # wait_time = between(1, 3)  # realistic pacing (recommended)
    # wait_time = between(0, 0)  # no wait (maximum load)
    
    def on_start(self):
        """Called when a user starts - performs setup"""

        # The osdu_perf  automatically injects all required headers
        # (Authorization, data-partition-id, Content-Type, correlation-id)
        # into every outgoing request. You do NOT need to pass headers manually.
        # Just write your tests — the framework handles the rest. if there is special case, you can add that alone in the header

        self.config_obj = PerformanceUser(self.environment)
        self.partition = self.config_obj.get_partition()
        self.host = self.config_obj.get_host()
        self.headers = self.config_obj.get_headers()
        self.appid = self.config_obj.get_appid()
        self.logger = self.config_obj.get_logger()

        self.logger.info(f"🚀 Started performance testing user")
        self.logger.info(f"   📍 Partition: {{self.partition}}")
        self.logger.info(f"   🌐 Host: {{self.host}}")
        self.logger.info(f"   🆔 App ID: {{self.appid or 'Not provided'}}")

    def on_stop(self):
        """Called when a user stops - performs cleanup"""
        self.logger.info("🛑 Stopped performance testing user")

    
    @tag("{service_name}")
    @task(1)
    def check_service_health(self):
        # No need to pass headers — middleware auto-injects auth, partition, correlation-id
        response = self.client.get("/api/storage/v2/liveness_check")
        self.logger.info(f"Health check status: ")

'''
        output_path.write_text(template, encoding='utf-8')
        print(f"[create_locustfile_template] Created {output_path.name}")

    def create_system_config_file(self, output_path: Path) -> None:
        """Creates system_config.yaml with key-only shared settings."""
        config_content = """# Shared system configuration for OSDU performance tests
# Keep environment and Azure Load Test location values here.

osdu_environment:
  # OSDU instance details (required for run local command)
  host:
  partition:
  app_id:

  performance_tier:
  version:

# OSDU deployment details (optional - used for metrics collection)
# Metrics Collection Configuration (optional)
# metrics_collector:
#   kusto:
#     cluster:
#     database:
#     ingest_uri:

test_environment:
  # Where the Azure Load Testing resource and tests are located
  subscription_id:
  resource_group:
  location:
"""
        output_path.write_text(config_content, encoding='utf-8')
        self.logger.info(f"Created {output_path.name}")

    def create_test_config_file(self, output_path: Path) -> None:
        """Creates test_config.yaml with key-only performance-tier/scenario fields."""
        config_content = """# Test configuration split from system settings.
# Supports per-performance-tier tuning with per-scenario overrides.
performance_tier_profiles:
  flex:
    default_wait_time:
      min:
      max:
    users:
    spawn_rate:
    run_time:
    engine_instances:

  standard:
    default_wait_time:
      min:
      max:
    users:
    spawn_rate:
    run_time:
    engine_instances:

  developer:
    default_wait_time:
      min:
      max:
    users:
    spawn_rate:
    run_time:
    engine_instances:

scenarios:
  # Required per scenario:
  # - Scenario key itself is the test scenario/tag (e.g., record_size_1KB)
  # - Provide test_name_prefix and test_run_id_description
  record_size_1KB:
    test_name_prefix:
    test_run_id_description:

  record_size_100KB:
    test_name_prefix:
    test_run_id_description:

  record_size_1MB:
    test_name_prefix:
    test_run_id_description:

  create_and_update_scenario:
    test_name_prefix:
    test_run_id_description:
"""
        output_path.write_text(config_content, encoding='utf-8')
        self.logger.info(f"Created {output_path.name}")

    # required 
    
    def _should_create_file(self, filepath: str, choice: str) -> bool:
        """
        Determine if a file should be created based on user choice and file existence.
        
        Args:
            filepath: Path to the file
            choice: User choice ('o', 's', 'b')
            
        Returns:
            True if file should be created, False otherwise
        """
        if choice == 'o':  # Overwrite
            return True
        elif choice == 's':  # Skip existing
            return not os.path.exists(filepath)
        elif choice == 'b':  # Backup (already done, now create new)
            return True
        return False

    def _create_file_if_needed(self, path: Path, creation_func, choice: str, *args) -> None:
        """A wrapper to create a file or skip it based on user choice."""
        if self._should_create_file(path, choice):
            path.parent.mkdir(parents=True, exist_ok=True)
            # Unpack the list of args if it's passed as a single list
            creation_func(path, *args[0] if isinstance(args[0], list) else args)
        else:
            print(f"⏭️  Skipped existing: {path.name}")

    def init_project(self, service_name: str, force: bool = False) -> None:
        """
        Initialize a new performance testing project for a specific service.
        
        Args:
            service_name: Name of the service to test (e.g., 'storage', 'search', 'wellbore')
            force: If True, overwrite existing files without prompting
        """
        project_name = f"perf_tests"
        test_filename = f"perf_{service_name}_test.py"
        project_path = Path.cwd() / project_name
        
        self.logger.info(f"[init_project] Initializing OSDU Performance Testing project for: {service_name}")
        
        # Check if project already exists
        if os.path.exists(project_name):
            self.logger.info(f"[init_project]  Directory '{project_name}' already exists!")

            # Check if specific service test file exists
            test_file_path = os.path.join(project_name, test_filename)
            if os.path.exists(test_file_path):
                self.logger.info(f"[init_project]  Test file '{test_filename}' already exists!")

                if force:
                    choice = 'o'  # Force overwrite
                    self.logger.info("[init_project] Force mode: Overwriting existing files...")
                else:
                    # Ask user what to do
                    while True:
                        choice = input(f"Do you want to:\n"
                                    f"  [o] Overwrite existing files\n"
                                    f"  [s] Skip existing files and create missing ones\n" 
                                    f"  [b] Backup existing files and create new ones\n"
                                    f"  [c] Cancel initialization\n"
                                    f"Enter your choice [o/s/b/c]: ").lower().strip()
                        
                        if choice in ['o', 'overwrite']:
                            self.logger.info("🔄 Overwriting existing files...")
                            break
                        elif choice in ['s', 'skip']:
                            self.logger.info("⏭️  Skipping existing files, creating missing ones...")
                            break
                        elif choice in ['b', 'backup']:
                            self.logger.info("💾 Creating backup of existing files...")
                            #_backup_existing_files(project_name, service_name)
                            break
                        elif choice in ['c', 'cancel']:
                            self.logger.info("❌ Initialization cancelled.")
                            return
                        else:
                            self.logger.info("❌ Invalid choice. Please enter 'o', 's', 'b', or 'c'.")
            else:
                # Directory exists but no service test file
                choice = 's' if not force else 'o'  # Skip mode or force
        else:
            choice = 'o'  # New project
            self.logger.info(f"[init_project] Creating new project directory: {project_name}")
            # Create project directory
            os.makedirs(project_name, exist_ok=True)
        
        files_to_create = [
            {"name": "requirements.txt", "creator": self.create_requirements_file, "args": []},
            {"name": "README.md", "creator": self.create_project_readme, "args": [service_name]},
            {"name": "locustfile.py", "creator": self.create_locustfile_template, "args": [service_name]},
            {"name": "config/system_config.yaml", "creator": self.create_system_config_file, "args": []},
            {"name": "config/test_config.yaml", "creator": self.create_test_config_file, "args": []},
        ]

        # Keep legacy config generation code in place, but disable it explicitly.
        if False:
            files_to_create.append({"name": "config.yaml", "creator": self.create_project_config, "args": [service_name]})
        
        for file_meta in files_to_create:
            file_path = project_path / file_meta["name"]
            self._create_file_if_needed(file_path, file_meta["creator"], choice, file_meta["args"])


        self.logger.info(f"Project {'updated' if choice == 's' else 'initialized'} successfully in {project_name}/")
        self.logger.info(f"Next steps:")
        self.logger.info(f"         1. cd {project_name}")
        self.logger.info(f"         2. pip install -r requirements.txt")
        self.logger.info(f"         3. Edit config/system_config.yaml to set your OSDU environment details")
        self.logger.info(f"         4. Edit config/test_config.yaml to define performance-tier/scenario test defaults")
        self.logger.info(f"         5. Edit locustfile.py to implement your test scenarios")
        self.logger.info(f"         6. Run local tests: osdu-perf run local --scenario record_size_1KB")
        self.logger.info(f"         7. Run Azure Load Tests: osdu-perf run azure_load_test --scenario record_size_1KB")
        self.logger.info(f"         8. Optional: Override config values with CLI arguments")
