"""
Local Test Runner for OSDU Performance Testing Framework.

This module provides an object-oriented interface for running local performance tests
using Locust with proper OSDU authentication and configuration.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

from .input_handler import InputHandler
from ..utils.logger import get_logger


@dataclass
class TestConfiguration:
    """
    Data class representing the complete test configuration.
    
    This encapsulates all the resolved parameters needed for test execution,
    including OSDU settings, test parameters, and generated identifiers.
    """
    host: str
    partition: str
    app_id: str
    token: Optional[str]
    test_run_id: str
    users: int
    spawn_rate: int
    run_time: str
    tags: str
    
    def to_env_dict(self) -> Dict[str, str]:
        """Convert configuration to environment variables dictionary."""
        env = {
            'HOST': self.host,
            'PARTITION': self.partition,
            'APPID': self.app_id,
            'TEST_RUN_ID': self.test_run_id,
            'TEST_SCENARIO': self.tags
        }
        
        if self.token:
            env['ADME_BEARER_TOKEN'] = self.token
            
        return env


class LocalTestRunner:
    """
    Handles the execution of local performance tests using Locust.
    
    This class encapsulates all the logic for:
    - Validating OSDU parameters
    - Setting up environment variables
    - Executing Locust commands with proper configuration
    """
    
    def __init__(self, logger=None):
        """
        Initialize the LocalTestRunner.
        
        Args:
            logger: Optional logger instance. If not provided, creates a default logger.
        """
        self.logger = logger or get_logger('local_test_runner')
        self._input_handler: Optional[InputHandler] = None
        self._test_config: Optional[TestConfiguration] = None

    def _get_input_handler(self, config_file: str) -> InputHandler:
        """Get or create InputHandler instance with configuration loaded."""
        if self._input_handler is None:
            self._input_handler = InputHandler(None)
            self._input_handler.load_from_config_file(config_file)
        return self._input_handler

    def _extract_osdu_parameters(self, args) -> Tuple[str, str, str, Optional[str]]:
        """Extract and validate OSDU parameters from config and CLI args."""
        input_handler = self._get_input_handler(args.config)
        
        host = input_handler.get_osdu_host(getattr(args, 'host', None))
        partition = input_handler.get_osdu_partition(getattr(args, 'partition', None))
        app_id = input_handler.get_osdu_app_id(getattr(args, 'app_id', None))
        token = input_handler.get_osdu_token(getattr(args, 'token', None))
        
        return host, partition, app_id, token
    
    def validate_osdu_parameters(self, args) -> bool:
        """
        Validate required OSDU parameters from config file and CLI arguments.
        
        Args:
            args: Argument namespace containing OSDU parameters and config file path
            
        Returns:
            True if all required parameters are present, False otherwise
        """
        try:
            host, partition, app_id, token = self._extract_osdu_parameters(args)
            
            self.logger.info("✅ OSDU Configuration validated:")
            self.logger.info(f"   Host: {host}")
            self.logger.info(f"   Partition: {partition}")
            self.logger.info(f"   App ID: {app_id}")
            self.logger.info(f"   Token: {'✓ Configured' if token else '❌ Not configured'}")
            
            return True
                
        except ValueError as ve:
            self.logger.error(f"❌ OSDU Configuration Error: {ve}")
            self.logger.info("💡 Make sure config.yaml contains required osdu_environment settings or provide CLI overrides:")
            self.logger.info("   --host <OSDU_HOST_URL>")
            self.logger.info("   --partition <PARTITION_ID>") 
            self.logger.info("   --app-id <APPLICATION_ID>")
            self.logger.info("   --token <BEARER_TOKEN>")
            return False
        except FileNotFoundError:
            self.logger.error(f"❌ Config file not found: {args.config}")
            self.logger.info("💡 Make sure the config file exists or run 'osdu-perf init <service>' to create a project structure")
            return False
        except Exception as e:
            self.logger.error(f"❌ Error loading config file: {e}")
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
            # Load the test configuration if not already loaded
            if self._test_config is None:
                self._test_config = self._load_test_configuration(args)
            
            # Generate base environment from current environment
            env = os.environ.copy()
            env.update(self._test_config.to_env_dict())
            
            return env
            
        except Exception as e:
            self.logger.error(f"❌ Error setting up environment variables: {e}")
            raise
    
    def list_available_locustfiles(self):
        """List available bundled locustfiles."""
        self.logger.info("📋 Available bundled locustfiles:")
        self.logger.info("  • Default comprehensive locustfile (includes all OSDU services)")
        self.logger.info("  • Use --locustfile option to specify a custom file")


    def prepare_locustfile(self, args) -> str:
        """
        Prepare the locustfile for execution.
        
        Args:
            args: Argument namespace containing locustfile parameters
            
        Returns:
            Path to the locustfile to use

        Raises:
            FileNotFoundError: If no locustfile is found
        """
        # Check if custom locustfile is specified and exists
        if hasattr(args, 'locustfile') and args.locustfile and Path(args.locustfile).exists():
            self.logger.info(f"🎯 Using custom locustfile: {args.locustfile}")
            return args.locustfile
        
        # Check if custom locustfile is specified but doesn't exist
        if hasattr(args, 'locustfile') and args.locustfile:
            raise FileNotFoundError(f"❌ Custom locustfile specified but not found: {args.locustfile}")


        # Check if locustfile.py exists in current directory (created during init)
        current_dir_locustfile = Path("locustfile.py")
        if current_dir_locustfile.exists():
            self.logger.info(f"✅ Using locustfile from current directory: {current_dir_locustfile}")
            return str(current_dir_locustfile)
        
        # No locustfile found - throw error instead of creating temporary one
        raise FileNotFoundError(
            "❌ No locustfile.py found in current directory.\n"
            "💡 Run 'osdu-perf init <service>' to create a project structure with locustfile.py\n"
            "   or use --locustfile to specify a custom locustfile path."
        )


    def build_locust_command(self, args, locustfile_path: str, test_config: TestConfiguration) -> List[str]:
        """
        Build the Locust command with all required parameters.
        
        Args:
            args: Argument namespace containing test parameters
            locustfile_path: Path to the locustfile to use
            test_config: Resolved test configuration
            
        Returns:
            List of command arguments for subprocess
        """
        locust_cmd = [
            "locust",
            "-f", locustfile_path,
            "--host", test_config.host,
            "--users", str(test_config.users),
            "--spawn-rate", str(test_config.spawn_rate),
            "--run-time", str(test_config.run_time),
            "--tags", test_config.tags,
        ]
        
        # Add headless/web-ui options
        # Default is web UI, use headless only if explicitly requested
        if hasattr(args, 'headless') and args.headless:
            locust_cmd.append("--headless")
        
        return locust_cmd

    def _load_test_configuration(self, args) -> TestConfiguration:
        """Load and resolve test configuration parameters into a data class."""
        input_handler = self._get_input_handler(args.config)
        
        # Get resolved parameters with CLI overrides
        host, partition, app_id, token = self._extract_osdu_parameters(args)
        
        users = input_handler.get_users(getattr(args, 'users', None))
        spawn_rate = input_handler.get_spawn_rate(getattr(args, 'spawn_rate', None))
        run_time = input_handler.get_run_time(getattr(args, 'run_time', None))
        tags = input_handler.get_test_scenario(getattr(args, 'test_scenario', None))
        
        # Generate test run ID using configured prefix
        test_run_id_prefix = input_handler.get_test_run_id_prefix()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_run_id = f"{test_run_id_prefix}_{timestamp}"
        
        self.logger.info(f"Generated Test Run ID: {test_run_id} and tags {tags}")

        if token is None:
            #need to make it better.
            token = self._input_handler.get_token_for_control_path(app_id)
        
        # Create and return the configuration data class
        config = TestConfiguration(
            host=host,
            partition=partition,
            app_id=app_id,
            token=token,
            test_run_id=test_run_id,
            users=users,
            spawn_rate=spawn_rate,
            run_time=run_time,
            tags=tags
        )
        
        return config

    def _execute_test_workflow(self, args, test_config: TestConfiguration) -> int:
        """Execute the complete test workflow."""
        try:
            # Set up environment variables
            env = self.setup_environment_variables(args)
            
            # Prepare locustfile
            locustfile_path = self.prepare_locustfile(args)
            
            # Build Locust command using resolved configuration
            locust_cmd = self.build_locust_command(args, locustfile_path, test_config)

            self.logger.info(f"Built locust command: {' '.join(locust_cmd)}")
            
            # Print test information
            is_web_ui = not (hasattr(args, 'headless') and args.headless)
            self.print_test_info(args, test_config, is_web_ui)
            
            # Execute the command
            exit_code = self.execute_locust_command(locust_cmd, env)
            
            # Print results
            if exit_code == 0:
                self.logger.info("Performance test completed successfully!")
            else:
                self.logger.error(f"Performance test failed with exit code: {exit_code}")

            return exit_code
        except FileNotFoundError as e:
            self.logger.error(str(e))
            return 1
    
    def print_test_info(self, args, test_config: TestConfiguration, is_web_ui: bool = False):
        """
        Print test configuration information.
        
        Args:
            args: Argument namespace containing test parameters
            test_config: Resolved test configuration
            is_web_ui: Whether running in web UI mode
        """
        if is_web_ui:
            self.logger.info("🌐 Starting Locust with Web UI...")
            self.logger.info("📊 Open http://localhost:8089 to access the web interface")
        else:
            self.logger.info("🚀 Starting headless performance test...")
        
        self.logger.info(f"🎯 Target Host: {test_config.host}")
        self.logger.info(f"🏷️  Data Partition: {test_config.partition}")
        self.logger.info(f"👥 Users: {test_config.users}, Spawn Rate: {test_config.spawn_rate}/s, Duration: {test_config.run_time}")
    
    def execute_locust_command(self, command: List[str], env: Dict[str, str]) -> int:
        """
        Execute the Locust command.
        
        Args:
            command: List of command arguments
            env: Environment variables dictionary
            
        Returns:
            Exit code from the subprocess
        """
        self.logger.info("⚡ Executing locust command...")
        try:
            result = subprocess.run(command, capture_output=False, text=True, env=env)
            return result.returncode
        except FileNotFoundError:
            self.logger.error("❌ Locust is not installed. Install it with: pip install locust")
            return 1
        except Exception as e:
            self.logger.error(f"❌ Error running locust command: {e}")
            return 1
        
    def pre_execution_validation(self, args) -> bool:
        """
        Template step: Perform pre-execution validation.
        
        This can be overridden to add different validation strategies.
        """
        # Handle special case first
        if hasattr(args, 'list_locustfiles') and args.list_locustfiles:
            self.list_available_locustfiles()
            return False  # Exit early, not an error
        
        return True
    
    def validate_test_parameters(self, args) -> bool:
        """
        Template step: Validate all required test parameters.
        
        This can be overridden for different parameter validation strategies.
        """
        return self.validate_osdu_parameters(args)

    def prepare_test_environment(self, args) -> None:
        """
        Template step: Prepare the test environment.
        
        This can be overridden to add different preparation strategies.
        """
        # Load configuration (this sets self._test_config)
        self._test_config = self._load_test_configuration(args)
        
        # Log preparation complete
        self.logger.info("✅ Test environment prepared successfully")

    def execute_test_suite(self, args) -> int:
        """
        Template step: Execute the actual test suite.
        
        This can be overridden for different execution strategies.
        """
        if self._test_config is None:
            raise RuntimeError("Test configuration not loaded. Call prepare_test_environment first.")
        
        return self._execute_test_workflow(args, self._test_config)

    def post_execution_cleanup(self, args, exit_code: int) -> None:
        """
        Template step: Perform post-execution cleanup.
        
        This can be overridden to add different cleanup strategies.
        """
        if exit_code == 0:
            self.logger.info("🎉 Test execution completed successfully!")
        else:
            self.logger.warning(f"⚠️ Test execution completed with issues (exit code: {exit_code})")
        
        # Future: Add any cleanup logic here (temp files, connections, etc.)

    def handle_execution_error(self, error: Exception) -> int:
        """
        Template step: Handle execution errors.
        
        This can be overridden for different error handling strategies.
        """
        self.logger.error(f"❌ Error during test execution: {error}")
        return 1
    
    def run_local_tests(self, args) -> int:
        """
        Run local performance tests using existing locust files.
        
        Args:
            args: Argument namespace containing all test parameters
            
        Returns:
            Exit code (0 for success, 1 for failure)
        """
        self.logger.info("Starting Local Performance Tests")
        try:
            # List available locustfiles if requested (do this first, no other params needed)
            if not self.pre_execution_validation(args):
                return 1
            
            if not self.validate_test_parameters(args):
                return 1
            
            self.prepare_test_environment(args)
            
            exit_code = self.execute_test_suite(args)
            
            self.post_execution_cleanup(args, exit_code)
            
            return exit_code
            
        except Exception as e:
            return self.handle_execution_error(e)