"""
CLI interface for the OSDU Performance Testing Framework.
"""

import argparse
import sys
import os
import shutil
import warnings
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Avoid importing the main package to prevent Locust imports
__version__ = "1.0.27"


def _backup_existing_files(project_name: str, service_name: str) -> None:
    """
    Create backup of existing project files.
    
    Args:
        project_name: Name of the project directory
        service_name: Name of the service
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"{project_name}_backup_{timestamp}"
    
    try:
        shutil.copytree(project_name, backup_dir)
        print(f"✅ Backup created at: {backup_dir}")
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        raise


def _should_create_file(filepath: str, choice: str) -> bool:
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


def init_project(service_name: str, force: bool = False) -> None:
    """
    Initialize a new performance testing project for a specific service.
    
    Args:
        service_name: Name of the service to test (e.g., 'storage', 'search', 'wellbore')
        force: If True, overwrite existing files without prompting
    """
    project_name = f"perf_tests"
    test_filename = f"perf_{service_name}_test.py"
    
    print(f"🚀 Initializing OSDU Performance Testing project for: {service_name}")
    
    # Check if project already exists
    if os.path.exists(project_name):
        print(f"⚠️  Directory '{project_name}' already exists!")
        
        # Check if specific service test file exists
        test_file_path = os.path.join(project_name, test_filename)
        if os.path.exists(test_file_path):
            print(f"⚠️  Test file '{test_filename}' already exists!")
            
            if force:
                choice = 'o'  # Force overwrite
                print("🔄 Force mode: Overwriting existing files...")
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
                        print("🔄 Overwriting existing files...")
                        break
                    elif choice in ['s', 'skip']:
                        print("⏭️  Skipping existing files, creating missing ones...")
                        break
                    elif choice in ['b', 'backup']:
                        print("💾 Creating backup of existing files...")
                        _backup_existing_files(project_name, service_name)
                        break
                    elif choice in ['c', 'cancel']:
                        print("❌ Initialization cancelled.")
                        return
                    else:
                        print("❌ Invalid choice. Please enter 'o', 's', 'b', or 'c'.")
        else:
            # Directory exists but no service test file
            choice = 's' if not force else 'o'  # Skip mode or force
            print(f"📁 Directory exists but '{test_filename}' not found. Creating missing files...")
    else:
        choice = 'o'  # New project
    
    # Create project directory
    os.makedirs(project_name, exist_ok=True)
    
    # Create sample test file
    test_file_path = os.path.join(project_name, test_filename)
    if _should_create_file(test_file_path, choice):
        create_service_test_file(service_name, test_file_path)
    else:
        print(f"⏭️  Skipped existing: {test_filename}")

    # Create requirements.txt
    requirements_path = os.path.join(project_name, "requirements.txt")
    if _should_create_file(requirements_path, choice):
        create_requirements_file(requirements_path)
    else:
        print(f"⏭️  Skipped existing: requirements.txt")

    # Create comprehensive README.md
    readme_path = os.path.join(project_name, "README.md")
    if _should_create_file(readme_path, choice):
        create_project_readme(service_name, readme_path)
    else:
        print(f"⏭️  Skipped existing: README.md")
    
    # Create locustfile.py for direct Locust testing
    locustfile_path = os.path.join(project_name, "locustfile.py")
    if _should_create_file(locustfile_path, choice):
        create_locustfile_template(locustfile_path, [service_name])
    else:
        print(f"⏭️  Skipped existing: locustfile.py")
    
    print(f"\n✅ Project {'updated' if choice == 's' else 'initialized'} successfully in {project_name}/")
    if choice != 's':
        print(f"✅ Created test file: {test_filename}")
    print(f"\n📝 Next steps:")
    print(f"   1. cd {project_name}")
    print("   2. pip install -r requirements.txt")
    print(f"   3. Edit {test_filename} to implement your test scenarios")
    print(f"   4. Run local tests: osdu-perf run local --host <host> --partition <partition> --token <token>")
    print(f"   5. Run Azure Load Tests: osdu_perf run azure_loadtest --subscription-id <sub-id> --resource-group <rg> --location <location> --host <host> --partition <partition> --token <token> --app-id <app-id>")



def create_service_test_file(service_name: str, output_path: str) -> None:
    """
    Create a service-specific test file following the perf_*_test.py pattern.
    
    Args:
        service_name: Name of the service
        output_path: Path where to create the test file
    """
    try:
        # Try to use the templates module
        from .templates.service_test_template import get_service_test_template
        formatted_template = get_service_test_template(service_name)
    except ImportError:
        # Fallback to embedded template if external file is not found
        service_name_clean = service_name.title()
        service_name_lower = service_name.lower()
        
        formatted_template = f'''import os
"""
Performance tests for {service_name_clean} Service
Generated by OSDU Performance Testing Framework
"""

from osdu_perf.core.base_service import BaseService


class {service_name_clean}PerformanceTest(BaseService):
    """
    Performance test class for {service_name_clean} Service
    
    This class will be automatically discovered and executed by the framework.
    """
    
    def __init__(self, client=None):
        super().__init__(client)
        self.name = "{service_name_lower}"
    
    def execute(self, headers=None, partition=None, base_url=None):
        """
        Execute {service_name_lower} performance tests
        
        Args:
            headers: HTTP headers including authentication
            partition: Data partition ID  
            base_url: Base URL for the service
        """
        print(f"🔥 Executing {{self.name}} performance tests...")
        
        # Example 1: Health check endpoint
        try:
            self._test_health_check(headers, base_url)
        except Exception as e:
            print(f"❌ Health check failed: {{e}}")
        
        # Example 2: Service-specific API calls
        try:
            self._test_service_apis(headers, partition, base_url)
        except Exception as e:
            print(f"❌ Service API tests failed: {{e}}")
        
        print(f"✅ Completed {{self.name}} performance tests")
    
    def provide_explicit_token(self) -> str:
        """
        Provide an explicit token for service execution.
        
        Returns the bearer token from environment variable set by localdev.py
        
        Returns:
            str: Authentication token for API requests
        """
        token = os.environ.get('ADME_BEARER_TOKEN', '')
        return token
  
    
    def prehook(self, headers=None, partition=None, base_url=None):
        """
        Pre-hook tasks before service execution.
        
        Use this method to set up test data, configurations, or prerequisites.
        
        Args:
            headers: HTTP headers including authentication
            partition: Data partition ID  
            base_url: Base URL for the service
        """
        print(f"🔧 Setting up prerequisites for {{self.name}} tests...")
        # TODO: Implement setup logic (e.g., create test data, configure environment)
        # Example: Create test records, validate partition access, etc.
        pass
    
    def posthook(self, headers=None, partition=None, base_url=None):
        """
        Post-hook tasks after service execution.
        
        Use this method for cleanup, reporting, or post-test validations.
        
        Args:
            headers: HTTP headers including authentication
            partition: Data partition ID  
            base_url: Base URL for the service
        """
        print(f"🧹 Cleaning up after {{self.name}} tests...")
        # TODO: Implement cleanup logic (e.g., delete test data, reset state)
        # Example: Remove test records, generate reports, validate cleanup
        pass
    
    def _test_health_check(self, headers, base_url):
        """Test health check endpoint"""
        try:
            response = self.client.get(
                f"{{base_url}}/api/{service_name_lower}/v1/health",
                headers=headers,
                name="{service_name_lower}_health_check"
            )
            print(f"Health check status: {{response.status_code}}")
        except Exception as e:
            print(f"Health check failed: {{e}}")
    
    def _test_service_apis(self, headers, partition, base_url):
        """
        Implement your service-specific test scenarios here
        
        Examples:
        - GET /api/{service_name_lower}/v1/records
        - POST /api/{service_name_lower}/v1/records
        - PUT /api/{service_name_lower}/v1/records/{{id}}
        - DELETE /api/{service_name_lower}/v1/records/{{id}}
        """
        
        # TODO: Replace with actual {service_name_lower} API endpoints
        
        # Example GET request
        try:
            response = self.client.get(
                f"{{base_url}}/api/{service_name_lower}/v1/info",
                headers=headers,
                name="{service_name_lower}_get_info"
            )
            print(f"Get info status: {{response.status_code}}")
        except Exception as e:
            print(f"Get info failed: {{e}}")


# Additional test methods can be added here
# Each method should follow the pattern: def test_scenario_name(self, headers, partition, base_url):
'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(formatted_template)

    print(f"✅ Created {service_name} test file at {output_path}")


def create_requirements_file(output_path: str) -> None:
    """
    Create a requirements.txt file with osdu_perf and its dependencies.
    
    Args:
        output_path: Path where to create the requirements.txt file
    """
    requirements_content = f"""# Performance Testing Requirements
# Install with: pip install -r requirements.txt

# OSDU Performance Testing Framework
osdu_perf=={__version__}

# Additional dependencies (if needed)
# locust>=2.0.0  # Already included with osdu_perf
# azure-identity>=1.12.0  # Already included with osdu_perf
# requests>=2.28.0  # Already included with osdu_perf
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(requirements_content)
    
    print(f"✅ Created requirements.txt at {output_path}")


def create_project_readme(service_name: str, output_path: str) -> None:
    """
    Create a comprehensive README for the performance testing project.
    
    Args:
        service_name: Name of the service being tested
        output_path: Path where to create the README
    """
    readme_content = f'''# {service_name.title()} Service Performance Tests

This project contains performance tests for the OSDU {service_name.title()} Service using the OSDU Performance Testing Framework.

## 📁 Project Structure

```
perf_tests/
├── locustfile.py              # Main Locust configuration
├── perf_{service_name}_test.py        # {service_name.title()} service tests
├── requirements.txt           # Python dependencies
└── README.md                 # This file
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Your Test Environment
Edit `perf_{service_name}_test.py` and update:
- API endpoints for {service_name} service
- Test data and scenarios
- Authentication requirements

### 3. Run Performance Tests
```bash
# Basic run with 10 users
locust -f locustfile.py --host https://your-api-host.com --partition your-partition --appid your-app-id

# Run with specific user count and spawn rate
locust -f locustfile.py --host https://your-api-host.com --partition your-partition --appid your-app-id -u 50 -r 5

# Run headless mode for CI/CD
locust -f locustfile.py --host https://your-api-host.com --partition your-partition --appid your-app-id --headless -u 10 -r 2 -t 60s
```

## 📝 Writing Performance Tests

### Test File Structure
Your test file `perf_{service_name}_test.py` follows this pattern:

```python
from osdu_perf.core.base_service import BaseService

class {service_name.title()}PerformanceTest(BaseService):
    def __init__(self, client=None):
        super().__init__(client)
        self.name = "{service_name}"
    
    def execute(self, headers=None, partition=None, base_url=None):
        # Your test scenarios go here
        self._test_health_check(headers, base_url)
        self._test_your_scenario(headers, partition, base_url)
```

### Key Points:
1. **Class Name**: Must end with `PerformanceTest` and inherit from `BaseService`
2. **File Name**: Must follow `perf_*_test.py` naming pattern for auto-discovery
3. **execute() Method**: Entry point for all your test scenarios
4. **HTTP Client**: Use `self.client` for making requests (pre-configured with Locust)

### Adding Test Scenarios

Create methods for each test scenario:

```python
def _test_create_record(self, headers, partition, base_url):
    \"\"\"Test record creation\"\"\"
    test_data = {{
        "kind": f"osdu:wks:{{partition}}:{service_name}:1.0.0",
        "data": {{"test": "data"}}
    }}
    
    response = self.client.post(
        f"{{base_url}}/api/{service_name}/v1/records",
        json=test_data,
        headers=headers,
        name="{service_name}_create_record"  # This appears in Locust UI
    )
    
    # Add assertions or validations
    assert response.status_code == 201, f"Expected 201, got {{response.status_code}}"
```

### HTTP Request Examples

```python
# GET request
response = self.client.get(
    f"{{base_url}}/api/{service_name}/v1/records/{{record_id}}",
    headers=headers,
    name="{service_name}_get_record"
)

# POST request with JSON
response = self.client.post(
    f"{{base_url}}/api/{service_name}/v1/records",
    json=data,
    headers=headers,
    name="{service_name}_create"
)

# PUT request
response = self.client.put(
    f"{{base_url}}/api/{service_name}/v1/records/{{record_id}}",
    json=updated_data,
    headers=headers,
    name="{service_name}_update"
)

# DELETE request
response = self.client.delete(
    f"{{base_url}}/api/{service_name}/v1/records/{{record_id}}",
    headers=headers,
    name="{service_name}_delete"
)
```

## 🔧 Configuration

### Required CLI Arguments
- `--host`: Base URL of your OSDU instance
- `--partition`: Data partition ID
- `--appid`: Azure AD Application ID

### Optional Arguments
- `-u, --users`: Number of concurrent users (default: 1)
- `-r, --spawn-rate`: User spawn rate per second (default: 1)
- `-t, --run-time`: Test duration (e.g., 60s, 5m, 1h)
- `--headless`: Run without web UI (for CI/CD)

### Authentication
The framework automatically handles Azure authentication using:
- Azure CLI credentials (for local development)
- Managed Identity (for cloud environments)
- Service Principal (with environment variables)

## 📊 Monitoring and Results

### Locust Web UI
- Open http://localhost:8089 after starting Locust
- Monitor real-time performance metrics
- View request statistics and response times
- Download results as CSV

### Key Metrics to Monitor
- **Requests per second (RPS)**
- **Average response time**  
- **95th percentile response time**
- **Error rate**
- **Failure count by endpoint**

## 🐛 Troubleshooting

### Common Issues

1. **Authentication Errors**
   ```
   Solution: Ensure Azure CLI is logged in or proper credentials are configured
   ```

2. **Import Errors**
   ```
   Solution: Run `pip install -r requirements.txt`
   ```

3. **Service Discovery Issues**
   ```
   Solution: Ensure test file follows perf_*_test.py naming pattern
   ```

4. **SSL/TLS Errors**
   ```
   Solution: Add --skip-tls-verify flag if using self-signed certificates
   ```

## 📚 Additional Resources

- [Locust Documentation](https://docs.locust.io/)
- [OSDU Performance Framework GitHub](https://github.com/janraj/osdu-perf)
- [Azure Authentication Guide](https://docs.microsoft.com/en-us/azure/developer/python/azure-sdk-authenticate)

## 🤝 Contributing

1. Follow the existing code patterns
2. Add comprehensive test scenarios
3. Update this README with new features
4. Test thoroughly before submitting changes

---

**Generated by OSDU Performance Testing Framework v1.0.5**
'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print(f"✅ Created comprehensive README at {output_path}")


def create_locustfile_template(output_path: str, service_names: Optional[List[str]] = None) -> None:
    """
    Create a locustfile.py template with the framework.
    
    Args:
        output_path: Path where to create the locustfile.py
        service_names: Optional list of service names to include in template
    """
    from .core.local_test_runner import LocalTestRunner
    
    # Use the LocalTestRunner to create the template
    runner = LocalTestRunner()
    runner.create_locustfile_template(output_path, service_names)


def create_service_template(service_name: str, output_dir: str) -> None:
    """
    Create a service template file (legacy - kept for backward compatibility).
    
    Args:
        service_name: Name of the service
        output_dir: Directory where to create the service file
    """
    template = f'''"""
{service_name} Service for Performance Testing
"""

from osdu_perf.core.base_service import BaseService


class {service_name.capitalize()}Service(BaseService):
    """
    Performance test service for {service_name}
    """
    
    def __init__(self, client=None):
        super().__init__(client)
        self.name = "{service_name}"
    
    def execute(self, headers=None, partition=None, base_url=None):
        """
        Execute {service_name} service tests
        
        Args:
            headers: HTTP headers including authentication
            partition: Data partition ID
            base_url: Base URL for the service
        """
        # TODO: Implement your service-specific test logic here
        
        # Example API call:
        # response = self.client.get(
        #     f"{{base_url}}/api/{service_name}/health",
        #     headers=headers,
        #     name="{service_name}_health_check"
        # )
        
        print(f"Executing {service_name} service tests...")
        pass
'''
    
    os.makedirs(output_dir, exist_ok=True)
    service_file = os.path.join(output_dir, f"{service_name}_service.py")
    
    with open(service_file, 'w', encoding='utf-8') as f:
        f.write(template)

    print(f"✅ Created {service_name} service template at {service_file}")


def create_localdev_file(output_path: str) -> None:
    """
    Create a localdev.py file for running Locust tests locally with ADME authentication.
    
    Args:
        output_path: Path where to create the localdev.py file
    """
    import os
    from pathlib import Path
    
    # Get the template from the separate file
    template_path = Path(__file__).parent / 'localdev_template.py'
    
    try:
        with open(template_path, 'r', encoding='utf-8') as template_file:
            localdev_content = template_file.read()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(localdev_content)
        
        print(f"✅ Created localdev.py at {output_path}")
        
    except FileNotFoundError:
        print(f"❌ Template file not found: {template_path}")
        print("Falling back to embedded template...")
        
        # Fallback to embedded template if separate file is missing
        localdev_content = '''#!/usr/bin/env python3
"""
Local Development CLI for OSDU Performance Testing Framework.
Runs Locust tests locally with ADME bearer token authentication.

Usage:
    python localdev.py --token "your_token" --partition "mypartition" --host "https://example.com"
"""

import argparse
import sys
import os
import subprocess
import glob

def main():
    """Main entry point for local development CLI."""
    parser = argparse.ArgumentParser(description="Local Development CLI for OSDU Performance Testing")
    parser.add_argument('--token', required=True, help='ADME bearer token for authentication')
    parser.add_argument('--partition', required=True, help='Data partition')
    parser.add_argument('--host', required=True, help='Target host URL')
    parser.add_argument('--users', '-u', type=int, help='Number of concurrent users')
    parser.add_argument('--spawn-rate', '-r', type=float, help='User spawn rate per second')
    parser.add_argument('--run-time', '-t', help='Test run time (e.g., 1h, 20m, 300s)')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--directory', '-d', default='.', help='Directory containing test files')
    
    args = parser.parse_args()
    
    print("🧪 OSDU Performance Testing - Local Development Mode")
    print("="*50)
    
    # Set environment variables
    os.environ['ADME_BEARER_TOKEN'] = args.token
    os.environ['PARTITION'] = args.partition
    
    # Build locust command
    cmd = ['locust', '-f', 'locustfile.py', '--host', args.host]
    
    if args.headless:
        cmd.append('--headless')
        if args.users:
            cmd.extend(['-u', str(args.users)])
        if args.spawn_rate:
            cmd.extend(['-r', str(args.spawn_rate)])
        if args.run_time:
            cmd.extend(['-t', args.run_time])
    
    print(f"🚀 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=args.directory)
    sys.exit(result.returncode)

if __name__ == '__main__':
    main()
'''
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(localdev_content)
        
        print(f"✅ Created localdev.py at {output_path} (using fallback template)")


def create_azureloadtest_file(output_path: str, service_name: str = None) -> None:
    """
    Create an azureloadtest.py file for running Azure Load Testing with automatic file upload.
    
    Args:
        output_path: Path where to create the azureloadtest.py file
        service_name: Name of the service (used for default load test naming)
    """
    azureloadtest_content = '''#!/usr/bin/env python3
"""
Azure Load Testing CLI for OSDU Performance Testing Framework.
Creates and executes Azure Load Tests with automatic test file upload.

Prerequisites:
    pip install azure-cli azure-identity azure-mgmt-loadtesting azure-mgmt-resource

Usage:
    python azureloadtest.py --subscription-id "your_subscription" --resource-group "your_rg" --location "eastus" --token "your_token" --partition "mypartition"
"""

import argparse
import sys
import os
from datetime import datetime

try:
    from osdu_perf.azure_loadtest_template import AzureLoadTestManager
except ImportError:
    print("❌ OSDU Performance Testing Framework not found.")
    print("Install with: pip install osdu_perf")
    sys.exit(1)


def validate_inputs(args) -> bool:
    """Validate required inputs for Azure Load Testing."""
    errors = []
    
    # Azure-specific validations
    if not args.subscription_id or not args.subscription_id.strip():
        errors.append("Azure subscription ID is required")
    
    if not args.resource_group or not args.resource_group.strip():
        errors.append("Resource group is required")
    
    if not args.location or not args.location.strip():
        errors.append("Azure location is required")
    
    # ADME-specific validations
    if not args.token or not args.token.strip():
        errors.append("Bearer token is required")
    
    if not args.partition or not args.partition.strip():
        errors.append("Partition is required")
    
    if errors:
        print("❌ Validation errors:")
        for error in errors:
            print(f"   • {error}")
        return False
    
    return True


def main():
    """Main entry point for Azure Load Testing CLI."""
    parser = argparse.ArgumentParser(
        description="Azure Load Testing CLI for OSDU Performance Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=\"\"\"
Examples:
  # Basic Azure Load Test
  python azureloadtest.py --subscription-id "12345678-1234-1234-1234-123456789012" --resource-group "myRG" --location "eastus" --token "your_token" --partition "mypartition"
  
  # With custom test settings
  python azureloadtest.py --subscription-id "12345678-1234-1234-1234-123456789012" --resource-group "myRG" --location "eastus" --token "your_token" --partition "mypartition" --users 100 --run-time 10m --engine-instances 3
\"\"\"
    )
    
    # Azure configuration
    parser.add_argument('--subscription-id', required=True, help='Azure subscription ID')
    parser.add_argument('--resource-group', required=True, help='Azure resource group')
    parser.add_argument('--location', required=True, help='Azure location (e.g., eastus, westus2)')
    parser.add_argument('--loadtest-name', default='osdu-perf-dev', help='Azure Load Testing resource name (default: osdu-perf-dev)')
    
    # ADME parameters
    parser.add_argument('--token', required=True, help='ADME bearer token for authentication')
    parser.add_argument('--partition', required=True, help='Data partition')
    
    # Test configuration
    parser.add_argument('--test-name', help='Test name (auto-generated if not provided)')
    parser.add_argument('--users', type=int, help='Number of concurrent users')
    parser.add_argument('--spawn-rate', type=float, help='User spawn rate per second')
    parser.add_argument('--run-time', help='Test run time (e.g., 10m, 300s)')
    parser.add_argument('--host', help='Target host URL')
    parser.add_argument('--engine-instances', type=int, help='Number of load generator instances')
    
    # Control options
    parser.add_argument('--force', action='store_true', help='Force overwrite existing tests without prompting')
    
    # Directory options
    parser.add_argument('--directory', '-d', default='.', help='Directory containing test files (default: current)')
    
    args = parser.parse_args()
    
    print("☁️  OSDU Performance Testing - Azure Load Testing Mode")
    print("="*60)
    
    # Validate inputs
    if not validate_inputs(args):
        sys.exit(1)
    
    # Check if directory exists
    if not os.path.exists(args.directory):
        print(f"❌ Directory not found: {args.directory}")
        sys.exit(1)
    
    # Initialize Azure Load Test Manager
    manager = AzureLoadTestManager(
        args.subscription_id,
        args.resource_group,
        args.location
    )
    
    # Authenticate with Azure
    if not manager.authenticate():
        sys.exit(1)
    
    # Detect service name if not provided in args
    detected_service = manager.detect_service_name(args.directory)
    if detected_service:
        print(f"🔍 Detected service: {detected_service}")
    
    # Generate names if not provided
    if not args.loadtest_name:
        if detected_service:
            args.loadtest_name = f"osdu-{detected_service}-loadtest"
        else:
            args.loadtest_name = f"osdu-loadtest-{int(__import__('time').time())}"
    
    if not args.test_name:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if detected_service:
            args.test_name = f"osdu_{detected_service}_test_{timestamp}"
        else:
            args.test_name = f"osdu_perf_test_{timestamp}"
    
    print(f"🏗️  Load Test Resource: {args.loadtest_name}")
    print(f"🧪 Test Name: {args.test_name}")
    
    # Create or get Load Testing resource
    if not manager.create_or_get_loadtest_resource(args.loadtest_name):
        sys.exit(1)
    
    # Check if test should be reused
    should_reuse, reason = manager.should_reuse_test(args.test_name, args.loadtest_name, args.force)
    if should_reuse is None:  # User cancelled
        print("❌ Operation cancelled by user")
        sys.exit(1)
    elif should_reuse:
        print(f"♻️  Reusing existing test: {args.test_name}")
        print(f"   Reason: {reason}")
        # Could add logic here to trigger a new run of existing test
        sys.exit(0)
    
    # Find test files
    test_files = manager.find_test_files(args.directory)
    if not test_files:
        print("❌ No test files found. Looking for perf_*test.py and locustfile.py")
        sys.exit(1)
    
    print(f"✅ Found {len(test_files)} test files:")
    for file in test_files:
        print(f"   • {file}")
    
    # Create test package
    zip_path = manager.create_test_zip(test_files, args.test_name, detected_service)
    
    # Create test configuration
    config = manager.create_test_configuration(args, args.test_name, detected_service)
    
    # Upload and run test
    success = manager.upload_and_run_test(args.loadtest_name, args.test_name, zip_path, config)
    
    if success:
        print("\\n✅ Azure Load Test completed successfully!")
        print(f"📊 Test Name: {args.test_name}")
        print(f"🌐 Resource Group: {args.resource_group}")
        print(f"📍 Location: {args.location}")
    else:
        print("\\n❌ Azure Load Test failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()
'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(azureloadtest_content)
    
    print(f"✅ Created azureloadtest.py at {output_path}")


def run_local_tests(args):
    """Run local performance tests using bundled locust files"""
    from .core.local_test_runner import LocalTestRunner
    
    # Create LocalTestRunner instance and run tests
    runner = LocalTestRunner()
    exit_code = runner.run_local_tests(args)
    
    if exit_code != 0:
        sys.exit(exit_code)


def run_azure_load_tests(args):
    """
    Create Azure Load Testing resources and prepare test files (Locust-independent).
    
    This function focuses purely on:
    1. Creating Azure Load Test resources via REST API
    2. Delegating file handling to AzureLoadTestRunner.setup_test_files()
    3. No Locust imports or dependencies to avoid monkey patching issues
    """
    import os
    from datetime import datetime
    
    print("🚀 Starting Azure Load Test Setup (Locust-independent)")
    print("=" * 60)
    
    # Import only the Azure runner (no Locust dependencies)
    try:
        from osdu_perf.core.azure_test_runner import AzureLoadTestRunner
    except ImportError as e:
        print(f"❌ Failed to import AzureLoadTestRunner: {e}")
        sys.exit(1)
    
    # Generate timestamp for unique naming
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Generate unique test name if not provided
    test_name = getattr(args, 'test_name', None)
    if not test_name:
        test_name = f"osdu_perf_test_{timestamp}"
    
    # Use the provided load test resource name (default: "osdu-perf-dev")
    loadtest_name = args.loadtest_name
    
    print(f"🏗️  Azure Subscription: {args.subscription_id}")
    print(f"🏗️  Resource Group: {args.resource_group}")
    print(f"🏗️  Location: {args.location}")
    print(f"🏗️  Load Test Resource: {loadtest_name}")
    print(f"🧪 Test Name: {test_name}")
    print("")
    
    # Create AzureLoadTestRunner instance
    runner = AzureLoadTestRunner(
        subscription_id=args.subscription_id,
        resource_group_name=args.resource_group,
        load_test_name=loadtest_name,
        location=args.location,
        tags={
            "Environment": "Performance Testing", 
            "Service": "OSDU", 
            "Tool": "osdu-perf",
            "TestName": test_name
        }
    )
    
    # Create the load test resource
    print("🔧 Creating Azure Load Test resource...")
    try:
        load_test = runner.create_load_test()
    except Exception as e:
        print(f"❌ Failed to create Azure Load Test resource: {e}")
        sys.exit(1)

    if not load_test:
        print("❌ Failed to create Azure Load Test resource")
        sys.exit(1)
        
    print("✅ Azure Load Test resource created successfully!")
    print("")
    
    # Get test directory from args
    test_directory = getattr(args, 'directory', './perf_tests')
    
    # Extract OSDU and load test parameters from args
    host = getattr(args, 'host', None)
    partition = getattr(args, 'partition', None)
    app_id = getattr(args, 'app_id', None)
    token = getattr(args, 'token', None)
    users = getattr(args, 'users', 10)
    spawn_rate = getattr(args, 'spawn_rate', 2)
    run_time = getattr(args, 'run_time', '60s')
    engine_instances = getattr(args, 'engine_instances', 1)
    
    # Setup test files (find, copy, upload) using the runner with OSDU parameters
    print("🔄 Setting up test files with OSDU configuration...")
    try:
        setup_success = runner.setup_test_files(
            test_name=test_name,
            test_directory=test_directory,
            host=host,
            partition=partition,
            app_id=app_id,
            token=token,
            users=users,
            spawn_rate=spawn_rate,
            run_time=run_time,
            engine_instances=engine_instances
        )
        if setup_success:
            print("✅ Test files setup completed successfully!")
            
            # Setup OSDU entitlements for the load test
            print("🔐 Setting up OSDU entitlements for load test...")
            try:
                entitlement_success = runner.setup_load_test_entitlements(
                    load_test_name=loadtest_name,
                    host=host,
                    partition=partition,
                    token=token
                )
                if entitlement_success:
                    print("✅ OSDU entitlements setup completed successfully!")
                else:
                    print("⚠️ Warning: OSDU entitlements setup completed with some issues")
                    print("📝 Check logs above for details. You may need to setup some entitlements manually")
            except Exception as e:
                print(f"⚠️ Warning: Failed to setup OSDU entitlements: {e}")
                print("📝 You may need to setup entitlements manually")
            
            # Trigger the load test execution
            print("🚀 Starting load test execution...")
            try:
                # Create a display name that fits Azure Load Testing constraints (2-50 characters)
                timestamp = datetime.now().strftime('%m%d_%H%M%S')  # Shorter timestamp
                base_name = test_name[:25] if len(test_name) > 25 else test_name  # Limit base name
                execution_display_name = f"{base_name}-{timestamp}"
                
                # Ensure total length doesn't exceed 50 characters
                if len(execution_display_name) > 50:
                    # Truncate base_name further if needed
                    max_base_length = 50 - len(f"{timestamp}")
                    base_name = test_name[:max_base_length] if len(test_name) > max_base_length else test_name
                    execution_display_name = f"{base_name}-{timestamp}"
                
                execution_result = runner.run_test(
                    test_name=test_name,  # Using a default test name for initial run
                    display_name="demo_tests"
                )
                import time
                print("⏳ Waiting 120 seconds for Azure Load Test to initialize...")
                time.sleep(120)

                execution_result = runner.run_test(
                    test_name=test_name,
                    display_name=execution_display_name
                )

                
                if execution_result:
                    execution_id = execution_result.get('testRunId', execution_result.get('name', execution_result.get('id', 'unknown')))
                    print("✅ Load test execution started successfully!")
                    print(f"   📊 Execution ID: {execution_id}")
                    print(f"   📊 Display Name: {execution_display_name} (length: {len(execution_display_name)})")
                    print(f"   🌐 Monitor progress in Azure Portal:")
                    print(f"       https://portal.azure.com/#@microsoft.onmicrosoft.com/resource/subscriptions/{args.subscription_id}/resourceGroups/{args.resource_group}/providers/Microsoft.LoadTestService/loadtests/{loadtest_name}/overview")
                else:
                    print("❌ Failed to start load test execution")
                    print("📝 Check Azure Load Testing resource in portal for manual execution")
            except Exception as e:
                print(f"⚠️ Warning: Failed to start load test execution: {e}")
                print("📝 You can manually start the test from Azure Portal")
            
            print("")
            print("🎉 Azure Load Test Setup Complete!")
            print("=" * 60)
        else:
            print("")
            print("⚠️ Azure Load Test Setup partially completed with issues")
            print("=" * 60)
            sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to setup test files: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="OSDU Performance Testing Framework CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  osdu-perf init storage              # Initialize tests for storage service
  osdu-perf init search --force       # Force overwrite existing files
  osdu-perf template wellbore         # Create template for wellbore service
  osdu-perf locustfile                # Create standalone locustfile
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize a new performance testing project')
    init_parser.add_argument('service_name', help='Name of the OSDU service to test (e.g., storage, search)')
    init_parser.add_argument('--force', action='store_true', help='Force overwrite existing files')
    
    # Template command (legacy)
    template_parser = subparsers.add_parser('template', help='Create a service template (legacy)')
    template_parser.add_argument('service_name', help='Name of the service')
    template_parser.add_argument('--output', '-o', default='.', help='Output directory')
    
    # Locustfile command
    locust_parser = subparsers.add_parser('locustfile', help='Create a standalone locustfile')
    locust_parser.add_argument('--output', '-o', default='locustfile.py', help='Output file path')
    
    # Version command
    version_parser = subparsers.add_parser('version', help='Show version information')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run performance tests')
    run_subparsers = run_parser.add_subparsers(dest='run_command', help='Run command options')
    
    # Run local subcommand
    local_parser = run_subparsers.add_parser('local', help='Run local performance tests using bundled locustfiles')
    
    # OSDU Connection Parameters (Required)
    local_parser.add_argument('--host', required=True, help='OSDU host URL (e.g., https://your-osdu-host.com)')
    local_parser.add_argument('--partition', '-p', required=True, help='OSDU data partition ID (e.g., opendes)')
    local_parser.add_argument('--token', required=True, help='Bearer token for OSDU authentication')
    
    # Locust Test Parameters (Optional)
    local_parser.add_argument('--users', '-u', type=int, default=10, help='Number of concurrent users (default: 10)')
    local_parser.add_argument('--spawn-rate', '-r', type=int, default=2, help='User spawn rate per second (default: 2)')
    local_parser.add_argument('--run-time', '-t', default='30m', help='Test duration (default: 30m)')
    
    # Advanced Options
    local_parser.add_argument('--locustfile', '-f', help='Specific locustfile to use (optional)')
    local_parser.add_argument('--list-locustfiles', action='store_true', help='List available bundled locustfiles')
    local_parser.add_argument('--headless', action='store_true', help='Run in headless mode (overrides web UI)')
    local_parser.add_argument('--web-ui', action='store_true', default=True, help='Run with web UI (default)')
    local_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    
    # Azure Load Test subcommand
    azure_parser = run_subparsers.add_parser('azure_load_test', help='Run performance tests on Azure Load Testing service')
    
    # Azure Configuration (Required)
    azure_parser.add_argument('--subscription-id', required=True, help='Azure subscription ID')
    azure_parser.add_argument('--resource-group', required=True, help='Azure resource group name')
    azure_parser.add_argument('--location', required=True, help='Azure region (e.g., eastus, westus2)')
    
    # OSDU Connection Parameters (Required) 
    azure_parser.add_argument('--host', required=True, help='OSDU host URL (e.g., https://your-osdu-host.com)')
    azure_parser.add_argument('--partition', '-p', required=True, help='OSDU data partition ID (e.g., opendes)')
    azure_parser.add_argument('--token', required=True, help='Bearer token for OSDU authentication')
    azure_parser.add_argument('--app-id', required=True, help='Azure AD Application ID for OSDU authentication')
    
    # Azure Load Testing Configuration (Optional)
    azure_parser.add_argument('--loadtest-name', default='osdu-perf-dev', help='Azure Load Testing resource name (default: osdu-perf-dev)')
    azure_parser.add_argument('--test-name', help='Test name (auto-generated if not provided)')
    azure_parser.add_argument('--engine-instances', type=int, default=1, help='Number of load generator instances (default: 1)')
    
    # Test Parameters (Optional)
    azure_parser.add_argument('--users', '-u', type=int, default=10, help='Number of concurrent users (default: 10)')
    azure_parser.add_argument('--spawn-rate', '-r', type=int, default=2, help='User spawn rate per second (default: 2)')
    azure_parser.add_argument('--run-time', '-t', default='30m', help='Test duration (default: 30m)')
    
    # Advanced Options
    azure_parser.add_argument('--directory', '-d', default='.', help='Directory containing perf_*_test.py files (default: current)')
    azure_parser.add_argument('--force', action='store_true', help='Force overwrite existing tests without prompting')
    azure_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'init':
            init_project(args.service_name, args.force)
        elif args.command == 'template':
            create_service_template(args.service_name, args.output)
        elif args.command == 'locustfile':
            create_locustfile_template(args.output)
        elif args.command == 'run':
            if args.run_command == 'local':
                run_local_tests(args)
            elif args.run_command == 'azure_load_test':
                # Suppress the false positive RuntimeWarning about coroutines
                warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*coroutine.*was never awaited.*")
                try:
                    run_azure_load_tests(args)
                finally:
                    warnings.resetwarnings()
            else:
                print("Available run commands: local, azure_load_test")
                return
        elif args.command == 'version':
            version_command()
        else:
            parser.print_help()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def create_parser():
    """Create and return the argument parser for the CLI"""
    parser = argparse.ArgumentParser(
        description="OSDU Performance Testing Framework CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  osdu-perf init storage              # Initialize tests for storage service
  osdu-perf init search --force       # Force overwrite existing files
  osdu-perf template wellbore         # Create template for wellbore service
  osdu-perf locustfile                # Create standalone locustfile
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize a new performance testing project')
    init_parser.add_argument('service_name', help='Name of the OSDU service to test (e.g., storage, search)')
    init_parser.add_argument('--force', action='store_true', help='Force overwrite existing files')
    
    # Template command (legacy)
    template_parser = subparsers.add_parser('template', help='Create a service template (legacy)')
    template_parser.add_argument('service_name', help='Name of the service')
    template_parser.add_argument('--output', '-o', default='.', help='Output directory')
    
    # Locustfile command
    locust_parser = subparsers.add_parser('locustfile', help='Create a standalone locustfile')
    locust_parser.add_argument('--output', '-o', default='locustfile.py', help='Output file path')
    
    # Version command
    version_parser = subparsers.add_parser('version', help='Show version information')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run performance tests')
    run_subparsers = run_parser.add_subparsers(dest='run_command', help='Run command options')
    
    # Run local subcommand
    local_parser = run_subparsers.add_parser('local', help='Run local performance tests using bundled locustfiles')
    
    # OSDU Connection Parameters (Required)
    local_parser.add_argument('--host', required=True, help='OSDU host URL (e.g., https://your-osdu-host.com)')
    local_parser.add_argument('--partition', '-p', required=True, help='OSDU data partition ID (e.g., opendes)')
    local_parser.add_argument('--token', required=True, help='Bearer token for OSDU authentication')
    
    # Locust Test Parameters (Optional)
    local_parser.add_argument('--users', '-u', type=int, default=10, help='Number of concurrent users (default: 10)')
    local_parser.add_argument('--spawn-rate', '-r', type=int, default=2, help='User spawn rate per second (default: 2)')
    local_parser.add_argument('--run-time', '-t', default='30m', help='Test duration (default: 30m)')
    
    # Advanced Options
    local_parser.add_argument('--locustfile', '-f', help='Specific locustfile to use (optional)')
    local_parser.add_argument('--list-locustfiles', action='store_true', help='List available bundled locustfiles')
    local_parser.add_argument('--headless', action='store_true', help='Run in headless mode (overrides web UI)')
    local_parser.add_argument('--web-ui', action='store_true', default=True, help='Run with web UI (default)')
    local_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    
    # Azure Load Test subcommand
    azure_parser = run_subparsers.add_parser('azure_load_test', help='Run performance tests on Azure Load Testing service')
    
    # Azure Configuration (Required)
    azure_parser.add_argument('--subscription-id', required=True, help='Azure subscription ID')
    azure_parser.add_argument('--resource-group', required=True, help='Azure resource group name')
    azure_parser.add_argument('--location', required=True, help='Azure region (e.g., eastus, westus2)')
    
    # OSDU Connection Parameters (Required) 
    azure_parser.add_argument('--host', required=True, help='OSDU host URL (e.g., https://your-osdu-host.com)')
    azure_parser.add_argument('--partition', '-p', required=True, help='OSDU data partition ID (e.g., opendes)')
    azure_parser.add_argument('--token', required=True, help='Bearer token for OSDU authentication')
    azure_parser.add_argument('--app-id', required=True, help='Azure AD Application ID for OSDU authentication')
    
    # Azure Load Testing Configuration (Optional)
    azure_parser.add_argument('--loadtest-name', default='osdu-perf-dev', help='Azure Load Testing resource name (default: osdu-perf-dev)')
    azure_parser.add_argument('--test-name', help='Test name (auto-generated if not provided)')
    azure_parser.add_argument('--engine-instances', type=int, default=1, help='Number of load generator instances (default: 1)')
    
    # Test Parameters (Optional)
    azure_parser.add_argument('--users', '-u', type=int, default=10, help='Number of concurrent users (default: 10)')
    azure_parser.add_argument('--spawn-rate', '-r', type=int, default=2, help='User spawn rate per second (default: 2)')
    azure_parser.add_argument('--run-time', '-t', default='30m', help='Test duration (default: 30m)')
    
    # Advanced Options
    azure_parser.add_argument('--directory', '-d', default='.', help='Directory containing perf_*_test.py files (default: current)')
    azure_parser.add_argument('--force', action='store_true', help='Force overwrite existing tests without prompting')
    azure_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    
    return parser


def get_available_locustfiles():
    """Get list of available locustfiles in the current directory and templates"""
    import glob
    from pathlib import Path
    
    available_files = []
    
    # Check current directory for locustfiles
    current_dir_files = glob.glob("locustfile*.py") + glob.glob("*locust*.py")
    for file in current_dir_files:
        available_files.append({
            'name': file,
            'path': file,
            'type': 'local',
            'description': f'Local locustfile: {file}'
        })
    
    # Add bundled templates
    available_files.append({
        'name': 'default',
        'path': 'bundled',
        'type': 'bundled',
        'description': 'Default OSDU comprehensive locustfile (auto-discovers perf_*_test.py files)'
    })
    
    available_files.append({
        'name': 'template',
        'path': 'template',
        'type': 'template',
        'description': 'Generate new locustfile template'
    })
    
    return available_files


def version_command():
    """Show version information"""
    print(f"OSDU Performance Testing Framework v{__version__}")
    print(f"Location: {Path(__file__).parent}")
    print("Dependencies:")
    
    try:
        import locust
        print(f"  • locust: {locust.__version__}")
    except ImportError:
        print("  • locust: not installed")
    
    try:
        import azure.identity
        print(f"  • azure-identity: {azure.identity.__version__}")
    except (ImportError, AttributeError):
        print("  • azure-identity: not installed")
    
    try:
        import requests
        print(f"  • requests: {requests.__version__}")
    except ImportError:
        print("  • requests: not installed")


if __name__ == "__main__":
    main()
