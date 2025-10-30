"""
CLI interface for the OSDU Performance Testing Framework.
"""
import argparse
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from . import __version__
from .utils.logger import get_logger

# Disable gevent support to avoid conflicts
os.environ.setdefault('GEVENT_SUPPORT', 'False')

# Initialize logger
logger = get_logger('cli')


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
        logger.info(f"✅ Backup created at: {backup_dir}")
    except Exception as e:
        logger.error(f"❌ Failed to create backup: {e}")
        raise



def run_local_tests(args):
    """Run local performance tests using bundled locust files."""
    logger.info("Starting Local Performance Tests")
    
    # Create LocalTestRunner instance with logger and run tests
    from osdu_perf.core.local_test_runner import LocalTestRunner
    runner = LocalTestRunner(logger=logger)
    exit_code = runner.run_local_tests(args)
    
    if exit_code != 0:
        sys.exit(exit_code)


def _load_azure_configuration(args):
    """Load and validate Azure Load Test configuration."""
    from osdu_perf.core.input_handler import InputHandler
    
    logger.info(f"Loading configuration from: {args.config}")
    input_handler = InputHandler(None)
    input_handler.load_from_config_file(args.config)
    
    # Get OSDU environment details from config with CLI overrides
    host = args.host or input_handler.get_osdu_host()
    partition = args.partition or input_handler.get_osdu_partition()
    osdu_adme_token = args.token  # Token is for running locally and enabling entitlement 
    app_id = args.app_id or input_handler.get_osdu_app_id()
    sku = getattr(args, 'sku', None) or input_handler.get_osdu_sku()
    version = getattr(args, 'version', None) or input_handler.get_osdu_version()
    
    # Get Azure Load Test configuration from config with CLI overrides
    subscription_id = args.subscription_id or input_handler.get_azure_subscription_id()
    resource_group = args.resource_group or input_handler.get_azure_resource_group()
    location = args.location or input_handler.get_azure_location()
    
    # Get test parameters
    users = input_handler.get_users(getattr(args, 'users', None))
    spawn_rate = input_handler.get_spawn_rate(getattr(args, 'spawn_rate', None))
    run_time = input_handler.get_run_time(getattr(args, 'run_time', None))
    engine_instances = input_handler.get_engine_instances(getattr(args, 'engine_instances', None))
    
    # Generate test run ID
    test_run_id_prefix = input_handler.get_test_run_id_prefix()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_run_id = f"{test_run_id_prefix}_{timestamp}"
    
    # Generate test name
    test_name = input_handler.get_test_name_prefix()
    test_name = f"{test_name}_{sku}_{version}".lower().replace(".", "_")
    tags = input_handler.get_test_scenario()
    
    execution_display_name = input_handler.get_test_run_name(test_name)
    
    return {
        'host': host,
        'partition': partition,
        'osdu_adme_token': osdu_adme_token,
        'app_id': app_id,
        'sku': sku,
        'version': version,
        'subscription_id': subscription_id,
        'resource_group': resource_group,
        'location': location,
        'users': users,
        'spawn_rate': spawn_rate,
        'run_time': run_time,
        'engine_instances': engine_instances,
        'test_run_id': test_run_id,
        'test_name': test_name,
        'tags': tags,
        'execution_display_name': execution_display_name,
        'timestamp': timestamp
    }


def _validate_azure_parameters(config):
    """Validate required Azure Load Test parameters."""
    # Validate required OSDU parameters
    if not config['host']:
        logger.error("❌ OSDU host URL is required (--host or config.yaml)")
        sys.exit(1)
    if not config['partition']:
        logger.error("❌ OSDU partition is required (--partition or config.yaml)")
        sys.exit(1)
    if not config['osdu_adme_token']:
        logger.error("❌ OSDU token is required (--token or config.yaml)")
        sys.exit(1)
        
    # Validate required Azure Load Test parameters
    if not config['subscription_id']:
        logger.error("❌ Azure subscription ID is required (--subscription-id or config.yaml)")
        sys.exit(1)
    if not config['resource_group']:
        logger.error("❌ Azure resource group is required (--resource-group or config.yaml)")
        sys.exit(1)
    if not config['location']:
        logger.error("❌ Azure location is required (--location or config.yaml)")
        sys.exit(1)


def _log_configuration_details(config):
    """Log configuration details for Azure Load Test."""
    logger.info(f"🌐 OSDU Host: {config['host']}")
    logger.info(f"📂 Partition: {config['partition']}")
    if config['app_id']:
        logger.info(f"🆔 App ID: {config['app_id']}")
    logger.info(f"📦 SKU: {config['sku']}")
    logger.info(f"🔢 Version: {config['version']}")
    logger.info(f"🆔 Test Run ID: {config['test_run_id']}")
    logger.info(f"🏗️  Azure Subscription: {config['subscription_id']}")
    logger.info(f"🏗️  Resource Group: {config['resource_group']}")
    logger.info(f"🏗️  Location: {config['location']}")
    logger.info(f"🧪 Test Name: {config['test_name']}")
    logger.info(f"     Test Scenario tags: {config['tags']}")


def _create_azure_test_runner(config, args):
    """Create and configure AzureLoadTestRunner instance."""
    from osdu_perf.core.azure_test_runner import AzureLoadTestRunner
    
    return AzureLoadTestRunner(
        subscription_id=config['subscription_id'],
        resource_group_name=config['resource_group'],
        load_test_name=args.loadtest_name,
        location=config['location'],
        tags={
            "Environment": "Performance Testing", 
            "Service": "OSDU", 
            "Tool": "osdu-perf",
            "TestName": config['test_name'],
            "TestRunId": config['test_run_id']
        },
        sku=config['sku'],
        version=config['version'],
        test_runid_name=config['execution_display_name']
    )


def _setup_azure_entitlements(runner, config, loadtest_name):
    """Setup OSDU entitlements for the load test."""
    logger.info("Setting up OSDU entitlements for load test...")
    try:
        entitlement_success = runner.setup_load_test_entitlements(
            load_test_name=loadtest_name,
            host=config['host'],
            partition=config['partition'],
            osdu_adme_token=config['osdu_adme_token']
        )
        if entitlement_success:
            logger.info("✅ OSDU entitlements setup completed successfully!")
        else:
            logger.warning("⚠️ OSDU entitlements setup completed with some issues")
            logger.warning("📝 Check logs above for details. You may need to setup some entitlements manually")
    except Exception as e:
        logger.warning(f"⚠️ Failed to setup OSDU entitlements: {e}")
        logger.warning("📝 You may need to setup entitlements manually")


def _execute_load_test(runner, config):
    """Execute the Azure Load Test."""
    # Wait for Azure Load Test to initialize
    initialization_wait_time = 360  # 6 minutes
    logger.info(f"STEP 4 Waiting {initialization_wait_time} seconds for Azure Load Test to initialize...")
    time.sleep(initialization_wait_time)

    # Trigger the load test execution
    logger.info("STEP 4 Starting load test execution...")
    try:
        execution_result = runner.run_test(
            test_name=config['test_name'],
            display_name=config['execution_display_name']
        )
        
        if execution_result:
            execution_id = execution_result.get('testRunId', 
                                             execution_result.get('name', 
                                                                execution_result.get('id', 'unknown')))
            logger.info("✅ STEP 4 Load test execution started successfully!")
            logger.info(f"  Execution ID: {execution_id}")
            logger.info(f"  Display Name: {config['execution_display_name']} (length: {len(config['execution_display_name'])})")
            logger.info("  Monitor progress in Azure Portal:")
            logger.info(f"  https://portal.azure.com/#@microsoft.onmicrosoft.com/resource/subscriptions/{config['subscription_id']}/resourceGroups/{config['resource_group']}/providers/Microsoft.LoadTestService/loadtests/{runner.load_test_name}/overview")
        else:
            logger.error("❌ STEP 4 Failed to start load test execution")
            logger.error("❌ STEP 4 Check Azure Load Testing resource in portal for manual execution")
    except Exception as e:
        logger.warning(f"STEP 4 Failed to start load test execution: {e}")
        logger.warning("STEP 4 You can manually start the test from Azure Portal")


def run_azure_load_tests(args):
    """
    Create Azure Load Testing resources and prepare test files (Locust-independent).
    
    This function focuses purely on:
    1. Loading config.yaml for OSDU connection details
    2. Creating Azure Load Test resources via REST API
    3. Delegating file handling to AzureLoadTestRunner.setup_test_files()
    4. No Locust imports or dependencies to avoid monkey patching issues
    """
    try:
        from osdu_perf.core.azure_test_runner import AzureLoadTestRunner
    except ImportError as e:
        logger.error(f"❌ Error importing AzureLoadTestRunner: {e}")
        sys.exit(1)
    
    logger.info("Starting Azure Load Test Setup (Config-driven)")
    logger.info("=" * 60)
    
    # Load and validate configuration
    config = _load_azure_configuration(args)
    _validate_azure_parameters(config)
    _log_configuration_details(config)
    
    logger.info(f"🏗️  Load Test Resource: {args.loadtest_name}")
    
    # Create AzureLoadTestRunner instance
    runner = _create_azure_test_runner(config, args)
    
    # Create the load test resource
    logger.info("Creating Azure Load Test resource...")
    try:
        load_test = runner.create_load_test_resource()
    except Exception as e:
        logger.error(f"❌ STEP 1 Failed to create Azure Load Test resource: {e}")
        sys.exit(1)

    if not load_test:
        logger.error("❌ STEP 1 Failed to create Azure Load Test resource")
        sys.exit(1)

    logger.info("✅ STEP 1 Azure Load Test resource created successfully!")
    logger.info("")
    
    # Get test directory from args
    test_directory = getattr(args, 'directory', './perf_tests')
    
    # Setup test files (find, copy, upload) using the runner with OSDU parameters
    logger.info("STEP 2 creating tests and uploading test files to azure load test resource...")
    try:
        setup_success = runner.create_tests_and_upload_test_files(
            test_name=config['test_name'],
            test_directory=test_directory,
            host=config['host'],
            partition=config['partition'],
            app_id=config['app_id'],
            users=config['users'],
            spawn_rate=config['spawn_rate'],
            run_time=config['run_time'],
            engine_instances=config['engine_instances'],
            tags=config['tags']
        )
        
        if setup_success:
            logger.info("✅ STEP 2 create tests and upload test files completed successfully!")
            
            # Setup OSDU entitlements for the load test
            _setup_azure_entitlements(runner, config, args.loadtest_name)
            
            # Execute the load test
            _execute_load_test(runner, config)

            logger.info("")
            logger.info("✅ Azure Load Test Setup Complete!")
            logger.info("=" * 60)
        else:
            logger.info("")
            logger.error("❌ Azure Load Test Setup partially completed with issues")
            logger.info("=" * 60)
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Failed to create and execute azure load tests: {e}")
        sys.exit(1)

def main():
    """Main CLI entry point for console script."""
    # Ensure gevent is disabled to avoid conflicts
    os.environ['GEVENT_SUPPORT'] = 'False'
    os.environ['NO_GEVENT_MONKEY_PATCH'] = '1'
    logger.debug(f"disable gevent monkey patch: {os.environ['NO_GEVENT_MONKEY_PATCH']}")

    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'init':
            from osdu_perf.core.init_runner import InitRunner
            init_runner = InitRunner()
            init_runner.init_project(args.service_name, args.force)

        elif args.command == 'run':
            if args.run_command == 'local':
                run_local_tests(args)
            elif args.run_command == 'azure_load_test':
                run_azure_load_tests(args)
            else:
                logger.error("❌ Available run commands: local, azure_load_test")
                return
        
        elif args.command == 'version':
            version_command()
        else:
            parser.print_help()
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)


def create_parser():
    """Create and return the argument parser for the CLI"""
    parser = argparse.ArgumentParser(
        description="OSDU Performance Testing Framework CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  osdu_perf init storage              # Initialize tests for storage service
  osdu_perf init search --force       # Force overwrite existing files
  osdu_perf version                   # Show version information
  osdu_perf run local --config config.yaml  # Run local performance tests
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize a new performance testing project')
    init_parser.add_argument('service_name', help='Name of the OSDU service to test (e.g., storage, search)')
    init_parser.add_argument('--force', action='store_true', help='Force overwrite existing files')
    
    # Version command
    version_parser = subparsers.add_parser('version', help='Show version information')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run performance tests')
    run_subparsers = run_parser.add_subparsers(dest='run_command', help='Run command options')
    
    # Run local subcommand
    local_parser = run_subparsers.add_parser('local', help='Run local performance tests using bundled locustfiles')
    
    # Configuration (Required)
    local_parser.add_argument('--config', '-c', required=True, help='Path to config.yaml file (required)')
    
    # OSDU Connection Parameters (Optional - overrides config.yaml values)
    local_parser.add_argument('--host', help='OSDU host URL (overrides config.yaml)')
    local_parser.add_argument('--partition', '-p', help='OSDU data partition ID (overrides config.yaml)')
    local_parser.add_argument('--token', required=True, help='Bearer token for OSDU authentication (required)')
    local_parser.add_argument('--app-id', help='Azure AD Application ID (overrides config.yaml)')
    local_parser.add_argument('--sku', help='OSDU SKU for metrics collection (overrides config.yaml, default: Standard)')
    local_parser.add_argument('--version', help='OSDU version for metrics collection (overrides config.yaml, default: 1.0)')
    # Locust Test Parameters (Optional)
    local_parser.add_argument('--users', '-u', type=int, help='Number of concurrent users (default: 100)')
    local_parser.add_argument('--spawn-rate', '-r', type=int, help='User spawn rate per second (default: 5)')
    local_parser.add_argument('--run-time', '-t', help='Test duration (default: 60m)')
    local_parser.add_argument('--engine-instances', '-e', type=int, help='Number of engine instances (default: 10)')
    # Advanced Options
    local_parser.add_argument('--locustfile', '-f', help='Specific locustfile to use (optional)')
    local_parser.add_argument('--list-locustfiles', action='store_true', help='List available bundled locustfiles')
    local_parser.add_argument('--headless', action='store_true', help='Run in headless mode (overrides web UI)')
    local_parser.add_argument('--web-ui', action='store_true', default=True, help='Run with web UI (default)')
    local_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    
    # Azure Load Test subcommand
    azure_parser = run_subparsers.add_parser('azure_load_test', help='Run performance tests on Azure Load Testing service')
    
    # Configuration (Required)
    azure_parser.add_argument('--config', '-c', required=True, help='Path to config.yaml file (required)')
    
    # Azure Configuration (Optional - can be read from config.yaml)
    azure_parser.add_argument('--subscription-id', help='Azure subscription ID (overrides config.yaml)')
    azure_parser.add_argument('--resource-group', help='Azure resource group name (overrides config.yaml)')
    azure_parser.add_argument('--location', help='Azure region (e.g., eastus, westus2) (overrides config.yaml)')
    
    # OSDU Connection Parameters (Optional - overrides config.yaml values)
    azure_parser.add_argument('--host', help='OSDU host URL (overrides config.yaml)')
    azure_parser.add_argument('--partition', '-p', help='OSDU data partition ID (overrides config.yaml)')
    azure_parser.add_argument('--token', required=True, help='Bearer token for OSDU authentication (required)')
    azure_parser.add_argument('--app-id', help='Azure AD Application ID (overrides config.yaml)')
    azure_parser.add_argument('--sku', help='OSDU SKU for metrics collection (overrides config.yaml, default: Standard)')
    azure_parser.add_argument('--version', help='OSDU version for metrics collection (overrides config.yaml, default: 1.0)')
    
    # Azure Load Testing Configuration (Optional)
    azure_parser.add_argument('--loadtest-name', default='osdu-perf-dev', help='Azure Load Testing resource name (default: osdu-perf-dev)')
    azure_parser.add_argument('--test-name', help='Test name (auto-generated if not provided)')
    
    
    # Advanced Options
    azure_parser.add_argument('--directory', '-d', default='.', help='Directory containing perf_*_test.py files (default: current)')
    azure_parser.add_argument('--force', action='store_true', help='Force overwrite existing tests without prompting')
    azure_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    
    return parser


def get_available_locustfiles():
    """Get list of available locustfiles in the current directory and templates."""
    import glob
    
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
    available_files.extend([
        {
            'name': 'default',
            'path': 'bundled',
            'type': 'bundled',
            'description': 'Default OSDU comprehensive locustfile (auto-discovers perf_*_test.py files)'
        },
        {
            'name': 'template',
            'path': 'template',
            'type': 'template',
            'description': 'Generate new locustfile template'
        }
    ])
    
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


if __name__ == "__main__":
    main()
