"""
Local Test Runner for OSDU Performance Testing Framework.

This module provides an object-oriented interface for running local performance tests
using Locust with proper OSDU authentication and configuration.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Dict
from .input_handler import InputHandler


class LocalTestRunner:
    """
    Handles the execution of local performance tests using Locust.
    
    This class encapsulates all the logic for:
    - Validating OSDU parameters
    - Setting up environment variables
    - Creating temporary locustfiles from templates
    - Executing Locust commands with proper configuration
    """
    
    def __init__(self):
        """Initialize the LocalTestRunner."""
        self.temp_files_created = []
    
    def validate_osdu_parameters(self, args) -> bool:
        """
        Validate required OSDU parameters from config file and CLI arguments.
        
        Args:
            args: Argument namespace containing OSDU parameters and config file path
            
        Returns:
            True if all required parameters are present, False otherwise
        """
        try:
            # Load configuration from the specified config file
            input_handler = InputHandler(None)  # Temporary instance for config loading
            input_handler.load_from_config_file(args.config)
            
            # Try to get required parameters with CLI overrides
            try:
                host = input_handler.get_osdu_host(getattr(args, 'host', None))
                partition = input_handler.get_osdu_partition(getattr(args, 'partition', None))
                app_id = input_handler.get_osdu_app_id(getattr(args, 'app_id', None))
                # Token is optional - can be provided via config, CLI, or environment
                token = input_handler.get_osdu_token(getattr(args, 'token', None))
                
                print(f"✅ OSDU Configuration validated:")
                print(f"   Host: {host}")
                print(f"   Partition: {partition}")
                print(f"   App ID: {app_id}")
                print(f"   Token: {'✓ Configured' if token else '❌ Not configured'}")
                
                return True
                
            except ValueError as ve:
                print(f"❌ OSDU Configuration Error: {ve}")
                print("💡 Make sure config.yaml contains required osdu_environment settings or provide CLI overrides:")
                print("   --host <OSDU_HOST_URL>")
                print("   --partition <PARTITION_ID>") 
                print("   --app-id <APPLICATION_ID>")
                print("   --token <BEARER_TOKEN>")
                return False
                
        except FileNotFoundError:
            print(f"❌ Config file not found: {args.config}")
            print("💡 Make sure the config file exists or run 'osdu-perf init <service>' to create a project structure")
            return False
        except Exception as e:
            print(f"❌ Error loading config file: {e}")
            return False
    
    def setup_environment_variables(self, args) -> Dict[str, str]:
        """
        Set up environment variables for OSDU parameters using config file with CLI overrides.
        
        Args:
            args: Argument namespace containing OSDU parameters and config file path
            
        Returns:
            Dictionary of environment variables
        """
        try:
            # Load configuration
            input_handler = InputHandler(None)
            input_handler.load_from_config_file(args.config)
            
            # Get parameters with CLI overrides
            host = input_handler.get_osdu_host(getattr(args, 'host', None))
            partition = input_handler.get_osdu_partition(getattr(args, 'partition', None))
            app_id = input_handler.get_osdu_app_id(getattr(args, 'app_id', None))
            token = input_handler.get_osdu_token(getattr(args, 'token', None))
            
            # Generate test run ID using configured prefix
            from datetime import datetime
            test_run_id_prefix = input_handler.get_test_run_id_prefix()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            test_run_id = f"{test_run_id_prefix}_{timestamp}"
            
            # Prepare environment variables
            env = os.environ.copy()
            env['HOST'] = host
            env['PARTITION'] = partition
            env['APPID'] = app_id
            env['TEST_RUN_ID'] = test_run_id
            
            # Add token if available
            if token:
                env['ADME_BEARER_TOKEN'] = token
            else:
                print("⚠️  No authentication token configured - tests may fail if token is required")
            
            return env
            
        except Exception as e:
            print(f"❌ Error setting up environment variables: {e}")
            raise
    
    def list_available_locustfiles(self):
        """List available bundled locustfiles."""
        print("📋 Available bundled locustfiles:")
        print("  • Default comprehensive locustfile (includes all OSDU services)")
        print("  • Use --locustfile option to specify a custom file")
    
    def create_locustfile_template(self, output_path: str, service_names: Optional[List[str]] = None) -> None:
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

import os
from locust import events
from osdu_perf import PerformanceUser


# STEP 1: Register custom CLI args with Locust
@events.init_command_line_parser.add_listener
def add_custom_args(parser):
    """Add OSDU-specific command line arguments"""
    parser.add_argument("--partition", type=str, default=os.getenv("PARTITION"), help="OSDU Data Partition ID")
    # Note: --host is provided by Locust built-in, no need to add it here
    # Note: --token is not exposed as CLI arg for security, only via environment variable
    parser.add_argument("--appid", type=str, default=os.getenv("APPID"), help="Azure AD Application ID")


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
        
        # Access OSDU parameters from Locust parsed options or environment variables
        partition = getattr(self.environment.parsed_options, 'partition', None) or os.getenv('PARTITION')
        host = getattr(self.environment.parsed_options, 'host', None) or self.host or os.getenv('HOST')
        token = os.getenv('ADME_BEARER_TOKEN')  # Token only from environment for security
        appid = getattr(self.environment.parsed_options, 'appid', None) or os.getenv('APPID')
        
        print(f"🚀 Started performance testing user")
        print(f"   📍 Partition: {{partition}}")
        print(f"   🌐 Host: {{host}}")
        print(f"   🔑 Token: {{'***' if token else 'Not provided'}}")
        print(f"   🆔 App ID: {{appid or 'Not provided'}}")
    
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
        self.temp_files_created.append(output_path)
    
    def prepare_locustfile(self, args) -> str:
        """
        Prepare the locustfile for execution.
        
        Args:
            args: Argument namespace containing locustfile parameters
            
        Returns:
            Path to the locustfile to use
        """
        # Check if custom locustfile is specified and exists
        if hasattr(args, 'locustfile') and args.locustfile and Path(args.locustfile).exists():
            print(f"🎯 Using custom locustfile: {args.locustfile}")
            return args.locustfile
        
        # Check if locustfile.py exists in current directory (created during init)
        current_dir_locustfile = Path("locustfile.py")
        if current_dir_locustfile.exists():
            print(f"🎯 Using existing locustfile from current directory: {current_dir_locustfile}")
            return str(current_dir_locustfile)
        
        # Create a temporary locustfile using our template
        temp_dir = tempfile.mkdtemp()
        locustfile_path = Path(temp_dir) / "locustfile.py"
        
        print("📝 Creating temporary locustfile from bundled template...")
        self.create_locustfile_template(str(locustfile_path))
        print(f"✅ Temporary locustfile created at: {locustfile_path}")
        
        return str(locustfile_path)
    
    def build_locust_command(self, args, locustfile_path: str) -> List[str]:
        """
        Build the Locust command with all required parameters.
        
        Args:
            args: Argument namespace containing test parameters
            locustfile_path: Path to the locustfile to use
            
        Returns:
            List of command arguments for subprocess
        """
        # Use resolved host from config if available, otherwise fall back to args.host
        host = getattr(self, 'resolved_config', {}).get('host') or getattr(args, 'host', None)
        
        if not host:
            raise ValueError("Host must be configured in config.yaml or provided via --host argument")
        
        locust_cmd = [
            "python", "-m", "locust",
            "-f", locustfile_path,
            "--host", host,
            "--users", str(args.users),
            "--spawn-rate", str(args.spawn_rate),
            "--run-time", args.run_time,
        ]
        
        # Add headless/web-ui options
        # Default is web UI, use headless only if explicitly requested
        if hasattr(args, 'headless') and args.headless:
            locust_cmd.append("--headless")
        
        return locust_cmd
    
    def print_test_info(self, args, is_web_ui: bool = False):
        """
        Print test configuration information.
        
        Args:
            args: Argument namespace containing test parameters
            is_web_ui: Whether running in web UI mode
        """
        if is_web_ui:
            print("🌐 Starting Locust with Web UI...")
            print(f"📊 Open http://localhost:8089 to access the web interface")
        else:
            print("🚀 Starting headless performance test...")
        
        # Use resolved config values if available
        resolved_config = getattr(self, 'resolved_config', {})
        host = resolved_config.get('host') or getattr(args, 'host', 'Not configured')
        partition = resolved_config.get('partition') or getattr(args, 'partition', 'Not configured')
        
        print(f"🎯 Target Host: {host}")
        print(f"🏷️  Data Partition: {partition}")
        print(f"👥 Users: {args.users}, Spawn Rate: {args.spawn_rate}/s, Duration: {args.run_time}")
    
    def execute_locust_command(self, command: List[str], env: Dict[str, str]) -> int:
        """
        Execute the Locust command.
        
        Args:
            command: List of command arguments
            env: Environment variables dictionary
            
        Returns:
            Exit code from the subprocess
        """
        print("⚡ Executing locust command...")
        try:
            result = subprocess.run(command, capture_output=False, text=True, env=env)
            return result.returncode
        except FileNotFoundError:
            print("❌ Locust is not installed. Install it with: pip install locust")
            return 1
        except Exception as e:
            print(f"❌ Error running locust command: {e}")
            return 1
    
    def cleanup_temp_files(self):
        """Clean up any temporary files created during execution."""
        for temp_file in self.temp_files_created:
            try:
                temp_path = Path(temp_file)
                if temp_path.exists():
                    temp_path.unlink()
                    # Also try to remove the temp directory if it's empty
                    try:
                        temp_path.parent.rmdir()
                    except OSError:
                        pass  # Directory not empty, that's okay
            except Exception:
                pass  # Best effort cleanup
    
    def run_local_tests(self, args) -> int:
        """
        Run local performance tests using bundled locust files.
        
        Args:
            args: Argument namespace containing all test parameters
            
        Returns:
            Exit code (0 for success, 1 for failure)
        """
        try:
            # List available locustfiles if requested (do this first, no other params needed)
            if hasattr(args, 'list_locustfiles') and args.list_locustfiles:
                self.list_available_locustfiles()
                return 0
            
            # Validate required OSDU parameters and get resolved values
            if not self.validate_osdu_parameters(args):
                return 1
            
            # Load configuration and resolve values for command building
            input_handler = InputHandler(None)
            input_handler.load_from_config_file(args.config)
            
            # Get resolved parameters with CLI overrides
            resolved_host = input_handler.get_osdu_host(getattr(args, 'host', None))
            resolved_partition = input_handler.get_osdu_partition(getattr(args, 'partition', None))
            resolved_app_id = input_handler.get_osdu_app_id(getattr(args, 'app_id', None))
            resolved_token = input_handler.get_osdu_token(getattr(args, 'token', None))
            
            # Generate test run ID using configured prefix
            from datetime import datetime
            test_run_id_prefix = input_handler.get_test_run_id_prefix()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            test_run_id = f"{test_run_id_prefix}_{timestamp}"
            
            print(f"🆔 Generated Test Run ID: {test_run_id}")
            
            # Store resolved values for command building
            self.resolved_config = {
                'host': resolved_host,
                'partition': resolved_partition,
                'app_id': resolved_app_id,
                'token': resolved_token,
                'test_run_id': test_run_id
            }
            
            # Set up environment variables
            env = self.setup_environment_variables(args)
            
            # Prepare locustfile
            locustfile_path = self.prepare_locustfile(args)
            
            # Build Locust command using resolved values
            locust_cmd = self.build_locust_command(args, locustfile_path)
            
            # Print test information
            # Default is web UI, headless only if explicitly requested
            is_web_ui = not (hasattr(args, 'headless') and args.headless)
            self.print_test_info(args, is_web_ui)
            
            # Execute the command
            exit_code = self.execute_locust_command(locust_cmd, env)
            
            # Print results
            if exit_code == 0:
                print("\n✅ Performance test completed successfully!")
            else:
                print(f"\n❌ Performance test failed with exit code: {exit_code}")
            
            return exit_code
            
        except Exception as e:
            print(f"❌ Error running local tests: {e}")
            return 1
        
        finally:
            # Clean up temporary files
            self.cleanup_temp_files()