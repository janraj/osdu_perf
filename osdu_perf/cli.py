"""
CLI interface for the OSDU Performance Testing Framework.
"""

import argparse
import sys
import os
import shutil
from datetime import datetime
from typing import List, Optional


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
    
    # Create locustfile.py
    locustfile_path = os.path.join(project_name, "locustfile.py")
    if _should_create_file(locustfile_path, choice):
        create_locustfile_template(locustfile_path, [service_name])
    else:
        print(f"⏭️  Skipped existing: locustfile.py")
    
    # Create sample test file
    test_file_path = os.path.join(project_name, test_filename)
    if _should_create_file(test_file_path, choice):
        create_service_test_file(service_name, test_file_path)
    else:
        print(f"⏭️  Skipped existing: {test_filename}")

    # Create comprehensive README.md
    readme_path = os.path.join(project_name, "README.md")
    if _should_create_file(readme_path, choice):
        create_project_readme(service_name, readme_path)
    else:
        print(f"⏭️  Skipped existing: README.md")
    
    print(f"\n✅ Project {'updated' if choice == 's' else 'initialized'} successfully in {project_name}/")
    if choice != 's':
        print(f"✅ Created test file: {test_filename}")
    print(f"\n📝 Next steps:")
    print(f"   1. cd {project_name}")
    print("   2. pip install -r requirements.txt")
    print(f"   3. Edit {test_filename} to implement your test scenarios")
    print(f"   4. Run: locust -f locustfile.py --host <your-api-host> --partition <partition> --appid <app-id>")


def create_service_test_file(service_name: str, output_path: str) -> None:
    """
    Create a service-specific test file following the perf_*_test.py pattern.
    
    Args:
        service_name: Name of the service
        output_path: Path where to create the test file
    """
    template = f'''"""
Performance tests for {service_name.title()} Service
Generated by OSDU Performance Testing Framework
"""

from osdu_perf import BaseService


class {service_name.title()}PerformanceTest(BaseService):
    """
    Performance test class for {service_name.title()} Service
    
    This class will be automatically discovered and executed by the framework.
    """
    
    def __init__(self, client=None):
        super().__init__(client)
        self.name = "{service_name}"
    
    def execute(self, headers=None, partition=None, base_url=None):
        """
        Execute {service_name} performance tests
        
        Args:
            headers: HTTP headers including authentication
            partition: Data partition ID  
            base_url: Base URL for the service
        """
        print(f"🔥 Executing {{self.name}} performance tests...")
        
        # Example 1: Health check endpoint
        self._test_health_check(headers, base_url)
        
        # Example 2: Service-specific API calls
        self._test_service_apis(headers, partition, base_url)
        
        print(f"✅ Completed {{self.name}} performance tests")
    
    def provide_explicit_token(self) -> str:
        """
        Provide an explicit token for service execution.
        
        Override this method if you need custom token logic.
        
        Returns:
            str: Authentication token for API requests
        """
        # TODO: Implement custom token logic if needed
        # Example: return "Bearer your-custom-token-here"
        return ""
    
    def prehook(self, headers=None, partition=None, host=None):
        """
        Pre-hook tasks before service execution.
        
        Use this method to set up test data, configurations, or prerequisites.
        
        Args:
            headers: HTTP headers including authentication
            partition: Data partition ID  
            host: Host URL for the service
        """
        print(f"🔧 Setting up prerequisites for {{self.name}} tests...")
        # TODO: Implement setup logic (e.g., create test data, configure environment)
        # Example: Create test records, validate partition access, etc.
        pass
    
    def posthook(self, headers=None, partition=None, host=None):
        """
        Post-hook tasks after service execution.
        
        Use this method for cleanup, reporting, or post-test validations.
        
        Args:
            headers: HTTP headers including authentication
            partition: Data partition ID  
            host: Host URL for the service
        """
        print(f"🧹 Cleaning up after {{self.name}} tests...")
        # TODO: Implement cleanup logic (e.g., delete test data, reset state)
        # Example: Remove test records, generate reports, validate cleanup
        pass
    
    def _test_health_check(self, headers, base_url):
        """Test health check endpoint"""
        try:
            response = self.client.get(
                f"{{base_url}}/api/{service_name}/v1/health",
                headers=headers,
                name="{service_name}_health_check"
            )
            print(f"Health check status: {{response.status_code}}")
        except Exception as e:
            print(f"Health check failed: {{e}}")
    
    def _test_service_apis(self, headers, partition, base_url):
        """
        Implement your service-specific test scenarios here
        
        Examples:
        - GET /api/{service_name}/v1/records
        - POST /api/{service_name}/v1/records
        - PUT /api/{service_name}/v1/records/{{id}}
        - DELETE /api/{service_name}/v1/records/{{id}}
        """
        
        # TODO: Replace with actual {service_name} API endpoints
        
        # Example GET request
        try:
            response = self.client.get(
                f"{{base_url}}/api/{service_name}/v1/info",
                headers=headers,
                name="{service_name}_get_info"
            )
            print(f"Get info status: {{response.status_code}}")
        except Exception as e:
            print(f"Get info failed: {{e}}")
        
        # Example POST request (uncomment and modify as needed)
        # try:
        #     test_data = {{
        #         "kind": "osdu:wks:{{partition}}:{service_name}:1.0.0",
        #         "acl": {{
        #             "viewers": [f"data.default.viewers@{{partition}}.example.com"],
        #             "owners": [f"data.default.owners@{{partition}}.example.com"]
        #         }},
        #         "legal": {{
        #             "legaltags": ["opendes-public-usa-dataset-1"],
        #             "otherRelevantDataCountries": ["US"]
        #         }},
        #         "data": {{
        #             "msg": "Hello from {service_name} performance test"
        #         }}
        #     }}
        #     
        #     response = self.client.post(
        #         f"{{base_url}}/api/{service_name}/v1/records",
        #         json=test_data,
        #         headers=headers,
        #         name="{service_name}_create_record"
        #     )
        #     print(f"Create record status: {{response.status_code}}")
        # except Exception as e:
        #     print(f"Create record failed: {{e}}")


# Additional test methods can be added here
# Each method should follow the pattern: def test_scenario_name(self, headers, partition, base_url):
'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(template)

    print(f"✅ Created {service_name} test file at {output_path}")


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
from osdu_perf import BaseService

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
    service_list = service_names or ["example"]
    services_comment = f"# This will auto-discover and run: perf_{service_list[0]}_test.py" if service_names else "# This will auto-discover and run all perf_*_test.py files"
    
    template = f'''"""
OSDU Performance Tests - Locust Configuration
Generated by OSDU Performance Testing Framework

{services_comment}
"""

from locust import events
from osdu_perf import PerformanceUser


# STEP 1: Register custom CLI args with Locust
@events.init_command_line_parser.add_listener
def add_custom_args(parser):
    """Add OSDU-specific command line arguments"""
    parser.add_argument("--partition", type=str, help="OSDU Data Partition ID", required=True)
    parser.add_argument("--appid", type=str, help="Azure AD Application ID", required=True)


class OSDUUser(PerformanceUser):
    """
    OSDU Performance Test User
    
    This class automatically:
    - Discovers all perf_*_test.py files in the current directory
    - Handles Azure authentication using --appid
    - Orchestrates test execution with proper headers and context
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
        super().on_start()
        print(f"🚀 Started performance testing user for partition: {{self.environment.parsed_options.partition}}")
    
    def on_stop(self):
        """Called when a user stops - performs cleanup"""
        print("🛑 Stopped performance testing user")


# Optional: Add custom tasks here if needed
# from locust import task
# 
# class CustomOSDUUser(OSDUUser):
#     @task(weight=1)
#     def custom_task(self):
#         """Custom task example"""
#         # Your custom test logic here
#         pass
'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(template)

    print(f"✅ Created locustfile.py at {output_path}")


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

from osdu_perf import BaseService


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


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="OSDU Performance Testing Framework CLI",
        epilog="""
Examples:
  osdu-perf init storage       # Initialize project for Storage service
  osdu-perf init search        # Initialize project for Search service
  osdu-perf init wellbore      # Initialize project for Wellbore service
  osdu-perf init storage --force  # Force overwrite existing files
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Init command - simplified to take only service name
    init_parser = subparsers.add_parser('init', help='Initialize a new performance testing project for a service')
    init_parser.add_argument('service_name', help='Service name (e.g., storage, search, wellbore)')
    init_parser.add_argument('--force', action='store_true', help='Force overwrite existing files without prompting')
    
    # Legacy commands for backward compatibility
    service_parser = subparsers.add_parser('create-service', help='(Legacy) Create a new service template')
    service_parser.add_argument('name', help='Service name')
    service_parser.add_argument('--output-dir', default='./services', help='Output directory (default: ./services)')
    
    locust_parser = subparsers.add_parser('create-locustfile', help='(Legacy) Create a locustfile.py template')
    locust_parser.add_argument('--output', default='./locustfile.py', help='Output path (default: ./locustfile.py)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'init':
            init_project(args.service_name, force=getattr(args, 'force', False))
        elif args.command == 'create-service':
            create_service_template(args.name, args.output_dir)
        elif args.command == 'create-locustfile':
            create_locustfile_template(args.output)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
