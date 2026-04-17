import sys
import time
from ..command_base import Command
from ...utils.logger import get_logger

class AzureLoadTestCommand(Command):
    """Command for running Azure Load Testing."""
    def __init__(self, logger):
        self.logger = logger

    def validate_args(self, args) -> bool:
        self.logger.info("Validating Azure Load Test command arguments...")
        if not hasattr(args, 'scenario') or not args.scenario:
            self.logger.error("❌ Exactly one --scenario value is required for Azure Load Tests")
            return False
        return True
    
    def execute(self, args) -> int:
        self.logger.info("Starting Azure Load Test execution...")
        try:
            if not self.validate_args(args):
                return 1
                
            # Existing Azure load test logic here
            from osdu_perf.operations.azure_test_operation import AzureLoadTestRunner
            
            config = self._load_azure_configuration(args)
            self._validate_azure_parameters(config)
            self._log_configuration_details(config)

            runner = self._create_azure_test_runner(config, args)

            # Create the load test resource
            load_test = runner.create_load_test_resource()
            if not load_test:
                self.logger.error("❌ Failed to create Azure Load Test resource")
                return 1
            
            # Continue with existing workflow...
            test_directory = getattr(args, 'directory', './perf_tests')
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
                tags=config['tags'],
                adme_token = config['osdu_adme_token'],
                test_description = config.get('test_description', '')
            )
            
            if setup_success:
                self._setup_azure_entitlements(runner, config, args.loadtest_name)
                self._execute_load_test(runner, config)
                return 0
            else:
                return 1
                
        except Exception as e:
            return self.handle_error(e)
        
    
    def _load_azure_configuration(self, args):
        """Load and validate Azure Load Test configuration."""
        from osdu_perf.operations.input_handler import InputHandler
        
        self.logger.info(f"Loading configuration from system={args.system_config}")
        input_handler = InputHandler(None)
        input_handler.load_from_split_config_files(args.system_config)
        
        # Get OSDU environment details from config with CLI overrides
        host = args.host or input_handler.get_osdu_host()
        partition = args.partition or input_handler.get_osdu_partition()
        osdu_adme_token = args.token  # Token is for running locally and enabling entitlement 
        app_id = args.app_id or input_handler.get_osdu_app_id()
        sku = getattr(args, 'sku', None) or input_handler.get_osdu_sku()
        version = getattr(args, 'version', None) or input_handler.get_osdu_version()
        
        if osdu_adme_token is None:
            osdu_adme_token = input_handler.get_token_for_control_path(app_id)

        # Get Azure Load Test configuration from config with CLI overrides
        subscription_id = args.subscription_id or input_handler.get_azure_subscription_id()
        resource_group = args.resource_group or input_handler.get_azure_resource_group()
        location = args.location or input_handler.get_azure_location()
        
        execution_settings = input_handler.resolve_test_execution_settings(
            scenario=getattr(args, 'scenario', None),
            users=getattr(args, 'users', None),
            spawn_rate=getattr(args, 'spawn_rate', None),
            run_time=getattr(args, 'run_time', None),
            engine_instances=getattr(args, 'engine_instances', None),
        )

        # Generate test name using shared formatter to keep local and Azure consistent.
        if getattr(args, 'test_name', None):
            test_name = str(args.test_name).lower().replace('.', '_')
        else:
            test_name = input_handler.generate_test_name(sku=sku, version=version)

        # Keep Azure test run metadata prefix behavior while using shared ID generator.
        test_run_id = input_handler.generate_test_run_id(prefix=input_handler.get_test_run_id_prefix())

        tags = execution_settings['tags']
        test_description = input_handler.get_test_run_id_description()
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
            'users': execution_settings['users'],
            'spawn_rate': execution_settings['spawn_rate'],
            'run_time': execution_settings['run_time'],
            'engine_instances': execution_settings['engine_instances'],
            'test_run_id': test_run_id,
            'test_name': test_name,
            'tags': tags,
            'test_description': test_description,
            'execution_display_name': execution_display_name
        }



    def _validate_azure_parameters(self, config):
        """Validate required Azure Load Test parameters."""
        # Validate required OSDU parameters
        if not config['host']:
            self.logger.error("❌ OSDU host URL is required (--host or system_config.yaml)")
            sys.exit(1)
        if not config['partition']:
            self.logger.error("❌ OSDU partition is required (--partition or system_config.yaml)")
            sys.exit(1)
            
        # Validate required Azure Load Test parameters
        if not config['subscription_id']:
            self.logger.error("❌ Azure subscription ID is required (--subscription-id or system_config.yaml)")
            sys.exit(1)
        if not config['resource_group']:
            self.logger.error("❌ Azure resource group is required (--resource-group or system_config.yaml)")
            sys.exit(1)
        if not config['location']:
            self.logger.error("❌ Azure location is required (--location or system_config.yaml)")
            sys.exit(1)


    def _log_configuration_details(self, config):
        """Log configuration details for Azure Load Test."""
        self.logger.info(f"🌐 OSDU Host: {config['host']}")
        self.logger.info(f"📂 Partition: {config['partition']}")
        if config['app_id']:
            self.logger.info(f"🆔 App ID: {config['app_id']}")
        self.logger.info(f"📦 SKU: {config['sku']}")
        self.logger.info(f"🔢 Version: {config['version']}")
        self.logger.info(f"🆔 Test Run ID: {config['test_run_id']}")
        self.logger.info(f"🏗️  Azure Subscription: {config['subscription_id']}")
        self.logger.info(f"🏗️  Resource Group: {config['resource_group']}")
        self.logger.info(f"🏗️  Location: {config['location']}")
        self.logger.info(f"🧪 Test Name: {config['test_name']}")
        self.logger.info(f"     Test Scenario tags: {config['tags']}")


    def _create_azure_test_runner(self, config, args):
        """Create and configure AzureLoadTestRunner instance."""
        from osdu_perf.operations.azure_test_operation import AzureLoadTestRunner
        
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



    def _setup_azure_entitlements(self, runner, config, loadtest_name):
        """Setup OSDU entitlements for the load test."""
        self.logger.info("Setting up OSDU entitlements for load test...")
        try:
            entitlement_success = runner.setup_load_test_entitlements(
                load_test_name=loadtest_name,
                host=config['host'],
                partition=config['partition'],
                osdu_adme_token=config['osdu_adme_token']
            )
            if entitlement_success:
                self.logger.info("✅ OSDU entitlements setup completed successfully!")
            else:
                self.logger.warning("⚠️ OSDU entitlements setup completed with some issues")
                self.logger.warning("📝 Check logs above for details. You may need to setup some entitlements manually")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to setup OSDU entitlements: {e}")
            self.logger.warning("📝 You may need to setup entitlements manually")


    def _execute_load_test(self, runner, config):
        """Execute the Azure Load Test."""
        # Wait for Azure Load Test to initialize
        initialization_wait_time = 360  # 6 minutes
        self.logger.info(f"STEP 4 Waiting {initialization_wait_time} seconds for Azure Load Test to initialize...")
        time.sleep(initialization_wait_time)

        # Trigger the load test execution
        self.logger.info("STEP 4 Starting load test execution...")
        try:
            execution_result = runner.run_test(
                test_name=config['test_name'],
                display_name=config['execution_display_name']
            )
            
            if execution_result:
                if isinstance(execution_result, dict):
                    execution_id = execution_result.get(
                        'testRunId',
                        execution_result.get('name', execution_result.get('id', config['execution_display_name']))
                    )
                else:
                    execution_id = (
                        getattr(execution_result, 'testRunId', None)
                        or getattr(execution_result, 'name', None)
                        or getattr(execution_result, 'id', None)
                        or config['execution_display_name']
                    )
                self.logger.info("✅ STEP 4 Load test execution started successfully!")
                self.logger.info(f"  Execution ID: {execution_id}")
                self.logger.info(f"  Display Name: {config['execution_display_name']} (length: {len(config['execution_display_name'])})")
                self.logger.info("  Monitor progress in Azure Portal:")
                self.logger.info(f"  https://portal.azure.com/#@microsoft.onmicrosoft.com/resource/subscriptions/{config['subscription_id']}/resourceGroups/{config['resource_group']}/providers/Microsoft.LoadTestService/loadtests/{runner.load_test_name}/overview")
            else:
                self.logger.error("❌ STEP 4 Failed to start load test execution")
                self.logger.error("❌ STEP 4 Check Azure Load Testing resource in portal for manual execution")
        except Exception as e:
            self.logger.warning(f"STEP 4 Failed to start load test execution: {e}")
            self.logger.warning("STEP 4 You can manually start the test from Azure Portal")

