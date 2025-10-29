"""
CLI interface for the OSDU Performance Testing Framework.
"""
import os

os.environ.setdefault('GEVENT_SUPPORT', 'False')
import argparse
import sys
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from . import __version__
from .utils.logger import get_logger

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
    """Run local performance tests using bundled locust files"""
    try:
        import gevent.monkey
        gevent.monkey.patch_all()
    except ImportError:
        pass

    logger.info("Starting Local Performance Tests")
    # Create LocalTestRunner instance and run tests
    from osdu_perf.core.input_handler import InputHandler
    from osdu_perf.core.local_test_runner import LocalTestRunner
    runner = LocalTestRunner()
    exit_code = runner.run_local_tests(args)
    
    if exit_code != 0:
        sys.exit(exit_code)


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
    
    from osdu_perf.core.input_handler import InputHandler
    
    
    # Load configuration
    logger.info(f"Loading configuration from: {args.config}")
    input_handler = InputHandler(None)  # Create instance for config-only mode
    input_handler.load_from_config_file(args.config)  # Load config from file
    
    # Get OSDU environment details from config with CLI overrides
    host = args.host or input_handler.get_osdu_host()
    partition = args.partition or input_handler.get_osdu_partition()
    osdu_adme_token = args.token or input_handler.get_osdu_token()
    app_id = args.app_id or input_handler.get_osdu_app_id()
    sku = getattr(args, 'sku', None) or input_handler.get_osdu_sku()
    version = getattr(args, 'version', None) or input_handler.get_osdu_version()
    
    # Get Azure Load Test configuration from config with CLI overrides
    subscription_id = args.subscription_id or input_handler.get_azure_subscription_id()
    resource_group = args.resource_group or input_handler.get_azure_resource_group()
    location = args.location or input_handler.get_azure_location()

    # Use already resolved OSDU parameters from config with CLI overrides (don't re-extract from args)
    # host, partition, token, app_id are already resolved above from config + CLI overrides
    users =  input_handler.get_users(getattr(args, 'users', None))
    spawn_rate = input_handler.get_spawn_rate(getattr(args, 'spawn_rate', None))
    run_time = input_handler.get_run_time(getattr(args, 'run_time', None))
    engine_instances = input_handler.get_engine_instances(getattr(args, 'engine_instances', None))
   
    
    # Generate test run ID using configured prefix
    test_run_id_prefix = input_handler.get_test_run_id_prefix()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_run_id = f"{test_run_id_prefix}_{timestamp}"
    
    # Validate required OSDU parameters
    if not host:
        logger.error("❌ OSDU host URL is required (--host or config.yaml)")
        sys.exit(1)
    if not partition:
        logger.error("❌ OSDU partition is required (--partition or config.yaml)")
        sys.exit(1)
    if not osdu_adme_token:
        logger.error("❌ OSDU token is required (--token or config.yaml)")
        sys.exit(1)
        
    # Validate required Azure Load Test parameters
    if not subscription_id:
        logger.error("❌ Azure subscription ID is required (--subscription-id or config.yaml azure_load_test.subscription_id)")
        sys.exit(1)
    if not resource_group:
        logger.error("❌ Azure resource group is required (--resource-group or config.yaml azure_load_test.resource_group)")
        sys.exit(1)
    if not location:
        logger.error("❌ Azure location is required (--location or config.yaml azure_load_test.location)")
        sys.exit(1)
    
    logger.info(f"🌐 OSDU Host: {host}")
    logger.info(f"📂 Partition: {partition}")
    if app_id:
        logger.info(f"🆔 App ID: {app_id}")
    logger.info(f"📦 SKU: {sku}")
    logger.info(f"🔢 Version: {version}")
    logger.info(f"🆔 Test Run ID: {test_run_id}")
    
    # Generate timestamp for unique naming
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Generate unique test name if not provided (use test_run_id as base)
    test_name = getattr(args, 'test_name', None)
    test_name = input_handler.get_test_name_prefix()
    test_name = f"{test_name}_{sku}_{version}".lower().replace(".", "_")

    if not test_name:
        test_name = test_run_id  # Use the generated test run ID as the test name
    
    #
    execution_display_name = input_handler.get_test_run_name(test_name)

    # Use the provided load test resource name (default: "osdu-perf-dev")
    loadtest_name = args.loadtest_name
    
    logger.info(f"🏗️  Azure Subscription: {subscription_id}")
    logger.info(f"🏗️  Resource Group: {resource_group}")
    logger.info(f"🏗️  Location: {location}")
    logger.info(f"🏗️  Load Test Resource: {loadtest_name}")
    logger.info(f"🧪 Test Name: {test_name}")
    logger.info("")
    
    # Create AzureLoadTestRunner instance
    runner = AzureLoadTestRunner(
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        load_test_name=loadtest_name,
        location=location,
        tags={
            "Environment": "Performance Testing", 
            "Service": "OSDU", 
            "Tool": "osdu-perf",
            "TestName": test_name,
            "TestRunId": test_run_id
        },
        sku=sku,
        version=version,
        test_runid_name=execution_display_name
    )
    
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
            test_name=test_name,
            test_directory=test_directory,
            host=host,
            partition=partition,
            app_id=app_id,
            token=osdu_adme_token,
            users=users,
            spawn_rate=spawn_rate,
            run_time=run_time,
            engine_instances=engine_instances
        )
        if setup_success:
            logger.info("✅ STEP 2 create tests and upload test files completed successfully!")
            
            
            # Setup OSDU entitlements for the load test
            logger.info("Setting up OSDU entitlements for load test...")
            try:
                entitlement_success = runner.setup_load_test_entitlements(
                    load_test_name=loadtest_name,
                    host=host,
                    partition=partition,
                    osdu_adme_token=osdu_adme_token
                )
                if entitlement_success:
                    logger.info("✅ OSDU entitlements setup completed successfully!")
                else:
                    logger.warning("⚠️ OSDU entitlements setup completed with some issues")
                    logger.warning("📝 Check logs above for details. You may need to setup some entitlements manually")
            except Exception as e:
                logger.warning(f"⚠️ Failed to setup OSDU entitlements: {e}")
                logger.warning("📝 You may need to setup entitlements manually")
            
            execution_result = runner.run_test(
                    test_name=test_name,
                    display_name="dummy_test"+timestamp
            )
                
            import time
            logger.info("STEP 4 Waiting 360 seconds for Azure Load Test to initialize...")
            time.sleep(360)

            # Trigger the load test execution
            logger.info("STEP 4 Starting load test execution...")
            try:
                execution_result = runner.run_test(
                    test_name=test_name,
                    display_name=execution_display_name
                )
                
                
                if execution_result:
                    execution_id = execution_result.get('testRunId', execution_result.get('name', execution_result.get('id', 'unknown')))
                    logger.info(f"✅ STEP 4 Load test execution started successfully!")
                    logger.info(f"  Execution ID: {execution_id}")
                    logger.info(f"  Display Name: {execution_display_name} (length: {len(execution_display_name)})")
                    logger.info(f"  Monitor progress in Azure Portal:")
                    logger.info(f"  https://portal.azure.com/#@microsoft.onmicrosoft.com/resource/subscriptions/{args.subscription_id}/resourceGroups/{args.resource_group}/providers/Microsoft.LoadTestService/loadtests/{loadtest_name}/overview")
                else:
                    logger.error("❌ STEP 4 Failed to start load test execution")
                    logger.error("❌ STEP 4 Check Azure Load Testing resource in portal for manual execution")
            except Exception as e:
                logger.warning(f"STEP 4 Failed to start load test execution: {e}")
                logger.warning(f"STEP 4 You can manually start the test from Azure Portal")

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

def apply_gevent_patch():
    """Apply gevent monkey patch only when needed for local Locust tests"""
    try:
        import gevent.monkey
        gevent.monkey.patch_all()
    except ImportError:
        pass

def main():
    """Main CLI entry point for console script"""

    """Main CLI entry point with init_manager parameter"""
    import os
    os.environ['GEVENT_SUPPORT'] = 'False'
    os.environ['NO_GEVENT_MONKEY_PATCH'] = '1'
    logger.debug(f"disable gevent monkey patch: {os.environ['NO_GEVENT_MONKEY_PATCH']}")

# Only apply monkey patching for local tests


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
                apply_gevent_patch()
                run_local_tests(args)
            elif args.run_command == 'azure_load_test':
                # Suppress the false positive RuntimeWarning about coroutines
                #warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*coroutine.*was never awaited.*")
                #try:
                run_azure_load_tests(args)
                #finally:
                #warnings.resetwarnings()
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
    local_parser.add_argument('--token', help='Bearer token for OSDU authentication (overrides config.yaml)')
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
    azure_parser.add_argument('--token', help='Bearer token for OSDU authentication (overrides config.yaml)')
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


if __name__ == "__main__":
    main()
