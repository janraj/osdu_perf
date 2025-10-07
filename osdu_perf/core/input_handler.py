import os
import logging
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

from .auth import AzureTokenManager


class InputHandler:
    def __init__(self, environment):
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        # Detect if running in Azure Load Testing environment (production)
        self.is_azure_load_test_env = self._detect_azure_load_test_environment()
        
        if self.is_azure_load_test_env:
            self.logger.info("Using Managed Identity authentication (Production)")
            self.partition = os.getenv("PARTITION", "default_partition")
            self.base_url = os.getenv("LOCUST_HOST", "https://default.url")
            self.app_id = os.getenv("APPID", "default_app_id")
            self.logger.info(f"Using environment variables - Host: {self.base_url} Partition: {self.partition} App ID: {self.app_id}")
        elif environment is not None:
            # Standard Locust environment mode
            self.logger.info(f"Host: {environment.host} Partition: {environment.parsed_options.partition} App ID: {environment.parsed_options.appid}")
            self.partition = environment.parsed_options.partition
            self.base_url = environment.host
            self.app_id = environment.parsed_options.appid
        else:
            # Config-only mode (used by CLI for parameter validation)
            self.logger.info("Config-only mode (no Locust environment)")
            self.partition = None
            self.base_url = None
            self.app_id = None
        
        # Only prepare headers if we have environment data
        if environment is not None or self.is_azure_load_test_env:
            self.header = self.prepare_headers()
        else:
            self.header = None
        
        # Load configuration for metrics collection and other settings
        self.config = self._load_config()
    
    def _find_config_file(self) -> Optional[Path]:
        """
        Find config.yaml file by searching current directory and parent directories.
        
        Returns:
            Path to config.yaml file if found, None otherwise.
        """
        # Search for config.yaml starting from current directory
        current_dir = Path.cwd()
        for directory in [current_dir] + list(current_dir.parents):
            config_file = directory / "config.yaml"
            if config_file.exists():
                self.logger.info(f"Found config file: {config_file}")
                return config_file
        
        self.logger.info("No config.yaml file found, using default values")
        return None
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Returns:
            Dictionary containing configuration, or empty dict if file not found.
        """
        config_file = self._find_config_file()
        
        if not config_file:
            return {}
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                self.logger.info(f"Successfully loaded configuration from {config_file}")
                return config
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing YAML configuration: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Error reading configuration file: {e}")
            return {}
    
    def _detect_azure_load_test_environment(self):
        """
        Detect if we're running in Azure Load Testing environment.
        
        Returns:
            bool: True if running in Azure Load Testing, False if local development
        """
        self.logger.info(f"Detecting Platform: AZURE_LOAD_TEST={os.getenv('AZURE_LOAD_TEST')}, PARTITION={os.getenv('PARTITION')}, LOCUST_HOST={os.getenv('LOCUST_HOST')}, APPID={os.getenv('APPID')}")

        # Check if any Azure Load Testing indicators are present
        if os.getenv("AZURE_LOAD_TEST") == "true":
            self.logger.info(f"Detected Azure Load Testing environment")
            return True

        if os.getenv("LOCUST_HOST", None) is not None:
            self.logger.info(f"Detected Azure Load Testing environment via LOCUST_HOST, PARTITION, APPID")
            return True

        if os.getenv("LOCUST_USERS", None) is not None:
            self.logger.info(f"Detected Azure Load Testing environment via LOCUST_USERS")
            return True
        
        if os.getenv("LOCUST_RUN_TIME", None) is not None:
            self.logger.info(f"Detected Azure Load Testing environment via LOCUST_RUN_TIME")
            return True
        
        if os.getenv("LOCUST_SPAWN_RATE", None) is not None:
            self.logger.info(f"Detected Azure Load Testing environment via LOCUST_SPAWN_RATE")
            return True
        
        self.logger.info("Detected local development environment")
        return False
    
    def prepare_headers(self):
        """
        Prepare headers for the HTTP client.
        Environment-aware authentication:
        - Local development (osdu_perf run local): Uses Azure CLI credentials
        - Azure Load Testing (osdu_perf run azure_load_test): Uses Managed Identity
        
        Returns:
            dict: Headers to be used in HTTP requests.
        """
        if self.is_azure_load_test_env:
            # Production: Use Managed Identity in Azure Load Testing
            self.logger.info("Using Managed Identity authentication (Production)")
            token_manager = AzureTokenManager(client_id=self.app_id, use_managed_identity=True)
        else:
            # Development: Use Azure CLI credentials locally
            self.logger.info("Using Azure CLI authentication (Development)")
            token_manager = AzureTokenManager(client_id=self.app_id, use_managed_identity=False)
            
        #token = token_manager.get_access_token("https://management.azure.com/.default") 

        token = token_manager.get_access_token(scope=f"api://{self.app_id}/.default")
        headers = {
            "Content-Type": "application/json",
            "x-data-partition-id": self.partition,
            "x-correlation-id": self.app_id,
            "Authorization": f"Bearer {token}"
        }
        return headers

    def get_kusto_config(self) -> Dict[str, Any]:
        """
        Get Kusto configuration with smart authentication selection.
        
        Uses default values when config.yaml is missing or incomplete.
        Config.yaml values override defaults when provided.
        
        Returns:
            Dictionary containing Kusto configuration with authentication method.
        """
        # Default Kusto configuration - used as fallback when config.yaml values are not provided
        default_config = {
            'cluster': 'https://testperfo.eastus.kusto.windows.net',
            'database': 'testperfo',
            'ingest_uri': 'https://ingest-testperfo.eastus.kusto.windows.net'
        }
        
        # Get configuration from file or use defaults
        metrics_config = self.config.get('metrics_collector', {})
        kusto_config = metrics_config.get('kusto', {})
        
        # Merge with defaults - only use non-empty values from config file
        final_config = default_config.copy()
        for key, value in kusto_config.items():
            if value and value.strip():  # Only use non-empty, non-whitespace values
                final_config[key] = value
        
        # Auto-detect authentication method based on execution environment
        if self.is_azure_load_test_env:
            final_config['auth_method'] = 'managed_identity'
            self.logger.info("Using Kusto authentication method: managed_identity (Azure Load Test environment)")
        else:
            final_config['auth_method'] = 'az_cli'
            self.logger.info("Using Kusto authentication method: az_cli (Local environment)")
        
        return final_config
    
    def get_metrics_collector_config(self) -> Dict[str, Any]:
        """
        Get complete metrics collector configuration.
        
        Returns:
            Dictionary containing all metrics collector configurations.
        """
        return self.config.get('metrics_collector', {})
    
    def is_kusto_enabled(self) -> bool:
        """
        Check if Kusto metrics collection is enabled.
        
        Returns:
            True if Kusto configuration is present, False otherwise.
        """
        kusto_config = self.get_kusto_config()
        # Consider Kusto enabled if we have at least cluster and database
        return bool(kusto_config.get('cluster') and kusto_config.get('database'))
    
    def get_test_settings(self) -> Dict[str, Any]:
        """
        Get test configuration settings with defaults.
        
        Returns:
            Dictionary containing test settings with fallback defaults.
        """
        # Default test settings
        default_test_settings = {
            'default_wait_time': {
                'min': 1,
                'max': 3
            },
            'default_users': 10,
            'default_spawn_rate': 2,
            'default_run_time': '60s',
            'test_run_id_prefix': 'osdu_perf_test'
        }
        
        # Get test settings from config file
        config_test_settings = self.config.get('test_settings', {})
        
        # Merge with defaults
        final_settings = default_test_settings.copy()
        if config_test_settings:
            # Deep merge for nested dictionaries like default_wait_time
            for key, value in config_test_settings.items():
                if key == 'default_wait_time' and isinstance(value, dict):
                    final_settings[key].update(value)
                else:
                    final_settings[key] = value
        
        return final_settings
    
    def get_wait_time_range(self) -> tuple:
        """
        Get wait time range for Locust users.
        
        Returns:
            Tuple of (min_wait, max_wait) in seconds.
        """
        test_settings = self.get_test_settings()
        wait_time = test_settings.get('default_wait_time', {'min': 1, 'max': 3})
        return (wait_time.get('min', 1), wait_time.get('max', 3))
    
    def get_default_users(self) -> int:
        """
        Get default number of users for performance tests.
        
        Returns:
            Default number of users.
        """
        test_settings = self.get_test_settings()
        return test_settings.get('default_users', 10)
    
    def get_default_spawn_rate(self) -> int:
        """
        Get default spawn rate for performance tests.
        
        Returns:
            Default spawn rate (users per second).
        """
        test_settings = self.get_test_settings()
        return test_settings.get('default_spawn_rate', 2)
    
    def get_default_run_time(self) -> str:
        """
        Get default run time for performance tests.
        
        Returns:
            Default run time as string (e.g., "60s", "5m").
        """
        test_settings = self.get_test_settings()
        return test_settings.get('default_run_time', '60s')
    
    def get_test_run_id_prefix(self) -> str:
        """
        Get test run ID prefix for performance tests.
        
        Returns:
            Test run ID prefix string (e.g., "osdu_perf_test").
        """
        test_settings = self.get_test_settings()
        return test_settings.get('test_run_id_prefix', 'osdu_perf_test')
    
    def get_osdu_host(self, cli_override: Optional[str] = None) -> str:
        """
        Get OSDU host URL from config.yaml or CLI override.
        
        Args:
            cli_override: Optional CLI argument value to override config
            
        Returns:
            OSDU host URL
            
        Raises:
            ValueError: If no host is configured and no CLI override provided
        """
        if cli_override:
            return cli_override
            
        osdu_env = self.config.get('osdu_environment', {})
        host = osdu_env.get('host')
        
        if not host or not host.strip():
            raise ValueError("OSDU host must be configured in config.yaml or provided via --host argument")
            
        return host.strip()
    
    def get_osdu_partition(self, cli_override: Optional[str] = None) -> str:
        """
        Get OSDU partition ID from config.yaml or CLI override.
        
        Args:
            cli_override: Optional CLI argument value to override config
            
        Returns:
            OSDU partition ID
            
        Raises:
            ValueError: If no partition is configured and no CLI override provided
        """
        if cli_override:
            return cli_override
            
        osdu_env = self.config.get('osdu_environment', {})
        partition = osdu_env.get('partition')
        
        if not partition or not partition.strip():
            raise ValueError("OSDU partition must be configured in config.yaml or provided via --partition argument")
            
        return partition.strip()
    
    def get_osdu_app_id(self, cli_override: Optional[str] = None) -> str:
        """
        Get OSDU Azure AD Application ID from config.yaml or CLI override.
        
        Args:
            cli_override: Optional CLI argument value to override config
            
        Returns:
            Azure AD Application ID
            
        Raises:
            ValueError: If no app_id is configured and no CLI override provided
        """
        if cli_override:
            return cli_override
            
        osdu_env = self.config.get('osdu_environment', {})
        app_id = osdu_env.get('app_id')
        
        if not app_id or not app_id.strip():
            raise ValueError("OSDU app_id must be configured in config.yaml or provided via --app-id argument")
            
        return app_id.strip()
    
    def get_osdu_token(self, cli_override: Optional[str] = None) -> Optional[str]:
        """
        Get OSDU authentication token from config.yaml or CLI override.
        
        Args:
            cli_override: Optional CLI argument value to override config
            
        Returns:
            Authentication token if available, None otherwise
        """
        if cli_override:
            return cli_override
            
        osdu_env = self.config.get('osdu_environment', {})
        auth_config = osdu_env.get('auth', {})
        token = auth_config.get('token')
        
        if token and token.strip():
            return token.strip()
            
        return None
    
    def load_from_config_file(self, config_path: str) -> None:
        """
        Load configuration from a specific config file path.
        
        Args:
            config_path: Path to the config.yaml file
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid YAML
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
            
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f) or {}
            self.logger.info(f"Loaded configuration from: {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file {config_path}: {e}")
        except Exception as e:
            raise ValueError(f"Error reading config file {config_path}: {e}")
