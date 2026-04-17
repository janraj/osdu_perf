import os
import logging
import socket
import threading
import yaml
import subprocess
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

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
            # Per-request correlation-id state (shared across users in this process/engine).
            # Counter is thread-safe to support gevent/threaded locust workers.
            self._test_run_id: Optional[str] = None
            self._short_hostname: str = self._compute_short_hostname()
            self._request_counter: int = 0
            self._counter_lock = threading.Lock()
            self.header = self.prepare_headers()
        else:
            self.header = None
            self._test_run_id = None
            self._short_hostname = self._compute_short_hostname()
            self._request_counter = 0
            self._counter_lock = threading.Lock()
        
        # Load split configuration files (system + test)
        self.system_config, self.test_config = self._load_split_configs()
        # Keep merged view for backward compatibility with internal callers.
        self.config = {**self.system_config, **self.test_config}
        self.selected_scenario: Optional[str] = None

    def _find_split_config_files(self) -> Dict[str, Optional[Path]]:
        """Find system/test config files, prioritizing config/ subfolder."""
        current_dir = Path.cwd()
        search_dirs = [current_dir] + list(current_dir.parents)

        found = {
            'system': None,
            'test': None,
        }

        for directory in search_dirs:
            if found['system'] is None:
                candidates = [
                    directory / 'config' / 'system_config.yaml',
                    directory / 'system_config.yaml',
                ]
                for system_file in candidates:
                    if system_file.exists():
                        found['system'] = system_file
                        self.logger.info(f"Found system config file: {system_file}")
                        break

            if found['test'] is None:
                candidates = [
                    directory / 'config' / 'test_config.yaml',
                    directory / 'test_config.yaml',
                ]
                for test_file in candidates:
                    if test_file.exists():
                        found['test'] = test_file
                        self.logger.info(f"Found test config file: {test_file}")
                        break

            if found['system'] is not None and found['test'] is not None:
                break

        if found['system'] is None:
            self.logger.info("No system_config.yaml file found, using defaults")
        if found['test'] is None:
            self.logger.info("No test_config.yaml file found, using defaults")

        return found

    def _load_yaml_file(self, path: Optional[Path]) -> Dict[str, Any]:
        """Load a YAML file safely and return a dictionary."""
        if path is None:
            return {}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f) or {}
                if not isinstance(content, dict):
                    self.logger.warning(f"YAML root must be a mapping in {path}; using empty config")
                    return {}
                return content
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing YAML configuration {path}: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Error reading configuration file {path}: {e}")
            return {}

    def _load_split_configs(self) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Load split configuration from system and test config files."""
        discovered = self._find_split_config_files()
        system_config = self._load_yaml_file(discovered['system'])
        test_config = self._load_yaml_file(discovered['test'])
        return system_config, test_config
    
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
    
    def get_token_for_control_path(self, app_id: str) -> Optional[str]:
        """
        Get token for control path based on app ID type.
        
        For Service Principals: Returns None (uses standard MI/CLI auth flow)
        For User Principals: Returns token from Azure CLI account
        
        Args:
            app_id: Azure AD app ID to check and get token for
            
        Returns:
            Token string if user principal, None if service principal or unknown
        """
        if not app_id:
            self.app_id_type = None
            return None
        
        app_id_info = self.check_app_id_type(app_id)
        if not app_id_info:
            self.app_id_type = 'unknown'
            self.logger.warning(f"Could not determine app ID type for: {app_id}")
            return None
        
        self.app_id_type = app_id_info['type']
        display_name = app_id_info['display_name']
        
        # Handler functions for each principal type
        handlers = {
            'service_principal': lambda: (
                self.logger.warning(f"✔️ Service Principal (App Registration): {display_name}. Ensure user OID is registered with ADME."),
                None
            )[1],
            
            'user': lambda: self._get_user_token(app_id, display_name),
            
            'unknown': lambda: (
                self.logger.warning(f"⚠ Unknown app ID type: {app_id}"),
                None
            )[1]
        }
        
        return handlers.get(self.app_id_type, lambda: None)()
    
    def _get_user_token(self, app_id: str, display_name: str) -> Optional[str]:
        """
        Helper method to get token for user principal.
        
        Args:
            app_id: Azure AD app ID
            display_name: Display name of the user principal
            
        Returns:
            Access token string or None if retrieval fails
        """
        self.logger.warning(f"⚠ App ID is a User Principal: {display_name}")
        self.logger.info("Using Azure CLI authentication for user principal")
        
        try:
            token_manager = AzureTokenManager(
                client_id=app_id, 
                use_managed_identity=False
            )
            return token_manager.az_account_get_access_token()
        except Exception as e:
            self.logger.error(f"Failed to get token for user principal: {e}")
            return None

    
    def check_app_id_type(self, app_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if the given app ID is a user (User Principal) or app registration (Service Principal).
        
        Args:
            app_id: Azure AD app ID (client ID or object ID) to check
            
        Returns:
            Dictionary with principal type information:
            {
                'type': 'user' | 'service_principal' | 'unknown',
                'display_name': str,
                'object_id': str,
                'details': dict  # Additional information
            }
            Returns None if unable to determine or on error
        """
        self.logger.info(f"Checking App ID type for: {app_id}")
        
        # Try service principal first
        sp_result = self._check_service_principal(app_id)
        if sp_result:
            return sp_result
        
        # Try user principal second
        user_result = self._check_user_principal(app_id)
        if user_result:
            return user_result
        
        # If neither worked, return unknown
        self.logger.warning(f"Could not determine type for app ID: {app_id}")
        return {
            'type': 'unknown',
            'display_name': 'Unknown',
            'object_id': 'Unknown',
            'app_id': app_id
        }
    
    def _check_service_principal(self, app_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if app ID is a service principal.
        
        Args:
            app_id: Azure AD app ID to check
            
        Returns:
            Dictionary with service principal info or None if not found
        """
        self.logger.debug(f"Checking if App ID is a Service Principal: {app_id}")
        try:
            result = subprocess.run(
                ['az', 'ad', 'sp', 'show', '--id', app_id],
                capture_output=True,
                text=True,
                check=True,
                shell=True
            )
            
            if result.returncode == 0:
                sp_info = json.loads(result.stdout)
                self.logger.info(
                    f"✓ App ID {app_id} is a Service Principal: "
                    f"{sp_info.get('displayName', 'N/A')}"
                )
                return {
                    'type': 'service_principal',
                    'display_name': sp_info.get('displayName', 'N/A'),
                    'object_id': sp_info.get('id', 'N/A'),
                    'app_id': sp_info.get('appId', 'N/A'),
                    'details': sp_info
                }
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Timeout checking service principal for: {app_id}")
        except json.JSONDecodeError as e:
            self.logger.debug(f"Invalid JSON from service principal check: {e}")
        except Exception as e:
            self.logger.debug(f"Not a service principal: {e}")
        
        return None
    
    def _check_user_principal(self, app_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if app ID is a user principal.
        
        Args:
            app_id: Azure AD app ID to check
            
        Returns:
            Dictionary with user principal info or None if not found
        """
        self.logger.info(f"Checking if App ID is a User Principal: {app_id}")
        try:
            result = subprocess.run(
                ['az', 'ad', 'user', 'show', '--id', app_id],
                capture_output=True,
                text=True,
                check=True,
                shell=True
            )
            
            if result.returncode == 0:
                user_info = json.loads(result.stdout)
                self.logger.info(
                    f"✓ App ID {app_id} is a User Principal: "
                    f"{user_info.get('displayName', 'N/A')}"
                )
                return {
                    'type': 'user',
                    'display_name': user_info.get('displayName', 'N/A'),
                    'object_id': user_info.get('id', 'N/A'),
                    'user_principal_name': user_info.get('userPrincipalName', 'N/A'),
                    'details': user_info
                }
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Timeout checking user principal for: {app_id}")
        except json.JSONDecodeError as e:
            self.logger.debug(f"Invalid JSON from user principal check: {e}")
        except Exception as e:
            self.logger.debug(f"Not a user principal: {e}")
        
        return None
    
    def prepare_headers(self):
        """
        Prepare headers for the HTTP client.
        Environment-aware authentication:
        - If token is provided via ADME_BEARER_TOKEN: Use the provided token
        - Local development (osdu_perf run local): Uses Azure CLI credentials
        - Azure Load Testing (osdu_perf run azure_load_test): Uses Managed Identity
        
        Returns:
            dict: Headers to be used in HTTP requests.
        """
        # Check if token is already provided via environment variable
        token = os.getenv('ADME_BEARER_TOKEN', None)
        
        if token:
            self.logger.info("Using provided token from ADME_BEARER_TOKEN environment variable")
        else:
            # No token provided, use authentication based on environment
            if self.is_azure_load_test_env:
                # Production: Use Managed Identity in Azure Load Testing
                self.logger.info("Using Managed Identity authentication (Production)")
                token_manager = AzureTokenManager(client_id=self.app_id, use_managed_identity=True)
            else:
                # Development: Use Azure CLI credentials locally
                self.logger.info("Using Azure CLI authentication (Development)")
                token_manager = AzureTokenManager(client_id=self.app_id, use_managed_identity=False)
                
            token = token_manager.get_access_token(scope=f"api://{self.app_id}/.default")
            
        test_run_id = os.getenv("TEST_RUN_ID_NAME", None) or os.getenv("TEST_RUN_ID", None)
        self.logger.info(f"Retrieved Test Run ID from environment: os.getenv('TEST_RUN_ID')={os.getenv('TEST_RUN_ID')}, os.getenv('TEST_RUN_ID_NAME')={os.getenv('TEST_RUN_ID_NAME')}")
        if test_run_id is None:
            test_run_id = self.get_test_run_id_prefix() + "-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")

        # Cache the base test run id so per-request correlation ids can be derived from it.
        self._test_run_id = test_run_id

        headers = {
            "Content-Type": "application/json",
            "data-partition-id": self.partition,
            "correlation-id": test_run_id,
            "Authorization": f"Bearer {token}"
        }
        return headers

    @staticmethod
    def _compute_short_hostname() -> str:
        """Return a short, header-safe hostname for correlation-id suffix.

        In Azure Load Testing each engine has a distinct hostname which lets us
        disambiguate counters across engines.
        """
        try:
            host = os.getenv("HOSTNAME") or socket.gethostname() or "unknown"
        except Exception:
            host = "unknown"
        # Keep only the first label (e.g. "engine-1" from "engine-1.internal")
        # and strip anything that isn't alphanumeric/dash/underscore.
        short = host.split('.')[0]
        safe = ''.join(ch for ch in short if ch.isalnum() or ch in ('-', '_'))
        return safe or "unknown"

    def _next_request_counter(self) -> int:
        with self._counter_lock:
            self._request_counter += 1
            return self._request_counter

    def new_correlation_id(self) -> str:
        """Generate a unique correlation-id for a single request.

        Format: ``<test_run_id>-<short_hostname>-<counter>``. The counter is
        per-process (per-engine), so combined with the hostname it is globally
        unique within a given test run.
        """
        base = self._test_run_id or (
            self.get_test_run_id_prefix() + "-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
        )
        return f"{base}-{self._short_hostname}-{self._next_request_counter()}"

    def build_request_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Return a fresh copy of the default headers with a unique correlation-id.

        Use this per-request so each outbound call gets its own correlation-id
        while preserving all other headers (auth, partition, content-type).
        """
        headers = dict(self.header or {})
        headers["correlation-id"] = self.new_correlation_id()
        if extra:
            headers.update(extra)
        return headers

    def get_kusto_config(self) -> Dict[str, Any]:
        """Get Kusto configuration with auto-selected auth method.

        Shape expected in system_config.yaml::

            azure_infra:
              kusto:
                cluster_uri: "https://<name>.<region>.kusto.windows.net"
                database: "<db>"

        Users only need to supply ONE of ``cluster_uri`` or ``ingest_uri``;
        the other is derived by adding/stripping the ``ingest-`` prefix on
        the hostname. Supplying both is allowed only if they're consistent.

        Returns:
            Dict with keys ``cluster_uri``, ``ingest_uri``, ``database``,
            ``auth_method``.
        """
        raw = (self._azure_infra_section().get('kusto') or {})

        def _clean(v):
            if isinstance(v, str):
                v = v.strip()
                return v or None
            return v or None

        cluster_uri = _clean(raw.get('cluster_uri'))
        ingest_uri = _clean(raw.get('ingest_uri'))
        database = _clean(raw.get('database'))

        if cluster_uri and not ingest_uri:
            ingest_uri = self._derive_kusto_ingest_uri(cluster_uri)
        elif ingest_uri and not cluster_uri:
            cluster_uri = self._derive_kusto_cluster_uri(ingest_uri)
        elif cluster_uri and ingest_uri:
            expected_ingest = self._derive_kusto_ingest_uri(cluster_uri)
            if expected_ingest and expected_ingest != ingest_uri:
                self.logger.warning(
                    f"kusto.cluster_uri and kusto.ingest_uri disagree "
                    f"(expected '{expected_ingest}' from cluster_uri, got "
                    f"'{ingest_uri}'); using the value derived from "
                    f"cluster_uri. Supply only one of these."
                )
                ingest_uri = expected_ingest

        auth_method = 'managed_identity' if self.is_azure_load_test_env else 'az_cli'
        self.logger.info(f"Using Kusto authentication method: {auth_method}")

        return {
            'cluster_uri': cluster_uri,
            'ingest_uri': ingest_uri,
            'database': database,
            'auth_method': auth_method,
        }

    @staticmethod
    def _derive_kusto_ingest_uri(cluster_uri: str) -> Optional[str]:
        """Given ``https://<name>.<region>.kusto.windows.net`` return
        ``https://ingest-<name>.<region>.kusto.windows.net``."""
        if not cluster_uri:
            return None
        try:
            scheme, rest = cluster_uri.split('://', 1)
        except ValueError:
            scheme, rest = 'https', cluster_uri
        host, _, path = rest.partition('/')
        if host.startswith('ingest-'):
            return f"{scheme}://{host}" + (f"/{path}" if path else "")
        return f"{scheme}://ingest-{host}" + (f"/{path}" if path else "")

    @staticmethod
    def _derive_kusto_cluster_uri(ingest_uri: str) -> Optional[str]:
        """Inverse of :meth:`_derive_kusto_ingest_uri`."""
        if not ingest_uri:
            return None
        try:
            scheme, rest = ingest_uri.split('://', 1)
        except ValueError:
            scheme, rest = 'https', ingest_uri
        host, _, path = rest.partition('/')
        if host.startswith('ingest-'):
            host = host[len('ingest-'):]
        return f"{scheme}://{host}" + (f"/{path}" if path else "")
    
    def is_kusto_enabled(self) -> bool:
        """True when a Kusto cluster and database are both configured."""
        kusto_config = self.get_kusto_config()
        return bool(kusto_config.get('cluster_uri') and kusto_config.get('database'))
    
    def get_test_settings(self) -> Dict[str, Any]:
        """
        Get test configuration settings with defaults.
        
        Returns:
            Dictionary containing test settings with fallback defaults.
        """
        # Defaults used when split config files are missing or partial.
        default_test_settings = {
            'default_wait_time': {
                'min': 1,
                'max': 3
            },
            'users': 10,
            'spawn_rate': 2,
            'run_time': '60s',
            'engine_instances': 1,
            'test_name_prefix': 'osdu_perf_test',
            'test_scenario': '',
            'test_run_id_description': 'Test run for osdu API',
        }

        profile_source = self.test_config.get('performance_tier_profiles', {}) or {}
        normalized_profiles = {
            str(key).lower(): value for key, value in profile_source.items()
        } if isinstance(profile_source, dict) else {}
        scenarios = self.test_config.get('scenarios', {}) or {}

        # Pick the performance-tier profile to use. Source of truth is the
        # `test_metadata.performance_tier` key in system_config.yaml.
        configured_tier = str(
            (self.system_config.get('test_metadata') or {}).get('performance_tier')
            or 'standard'
        ).lower()
        selected_profile = (
            normalized_profiles.get(configured_tier)
            or normalized_profiles.get('standard')
            or {}
        )

        configured_scenario = self.selected_scenario or os.getenv('TEST_SCENARIO')
        selected_scenario = {}
        selected_scenario_name = configured_scenario or ''
        if configured_scenario and configured_scenario in scenarios:
            selected_scenario = scenarios.get(configured_scenario, {})
        elif scenarios:
            selected_scenario_name = next(iter(scenarios.keys()))
            selected_scenario = scenarios.get(selected_scenario_name, {})

        final_settings = default_test_settings.copy()
        if isinstance(selected_profile, dict):
            for key, value in selected_profile.items():
                if key == 'default_wait_time' and isinstance(value, dict):
                    final_settings[key].update({k: v for k, v in value.items() if v is not None})
                elif value is not None:
                    final_settings[key] = value

        if isinstance(selected_scenario, dict):
            for key, value in selected_scenario.items():
                if value is not None:
                    final_settings[key] = value

        if not final_settings.get('test_scenario'):
            final_settings['test_scenario'] = selected_scenario_name
        if not final_settings.get('test_run_id_prefix'):
            final_settings['test_run_id_prefix'] = final_settings.get('test_name_prefix', 'osdu_perf_test')
        
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

    def get_users(self, cli_override: Optional[int] = None) -> int:
        """
        Get default number of users for performance tests.
        
        Returns:
            Default number of users.
        """
        if cli_override:
            return cli_override
        test_settings = self.get_test_settings()
        return test_settings.get('users', 100)

    def get_spawn_rate(self, cli_override: Optional[int] = None) -> int:
        """
        Get default spawn rate for performance tests.
        
        Returns:
            Default spawn rate (users per second).
        """
        if cli_override:
            return cli_override
        test_settings = self.get_test_settings()
        return test_settings.get('spawn_rate', 5)

    def get_run_time(self, cli_override: Optional[str] = None) -> str:
        """
        Get default run time for performance tests.
        
        Returns:
            Default run time as string (e.g., "60s", "5m").
        """
        if cli_override:
            return cli_override

        test_settings = self.get_test_settings()
        return test_settings.get('run_time', '3600s')
    

    def get_engine_instances(self, cli_override: Optional[int] = None) -> int:
        """
        Get default number of engine instances for performance tests.

        Returns:
            Default number of engine instances.
        """
        if cli_override:
            return cli_override
        test_settings = self.get_test_settings()
        return test_settings.get('engine_instances', 10)

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
            
        osdu_env = self.system_config.get('osdu_environment', {})
        host = osdu_env.get('host')
        
        if not host or not host.strip():
            raise ValueError("OSDU host must be configured in system_config.yaml or provided via --host argument")
            
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
            
        osdu_env = self.system_config.get('osdu_environment', {})
        partition = osdu_env.get('partition')
        
        if not partition or not partition.strip():
            raise ValueError("OSDU partition must be configured in system_config.yaml or provided via --partition argument")
            
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
            
        osdu_env = self.system_config.get('osdu_environment', {})
        app_id = osdu_env.get('app_id')
        
        if not app_id or not app_id.strip():
            raise ValueError("OSDU app_id must be configured in system_config.yaml or provided via --app-id argument")
            
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
            
        return None

    def _azure_infra_section(self) -> Dict[str, Any]:
        """Return the ``azure_infra`` section from system_config.yaml."""
        return self.system_config.get('azure_infra') or {}

    def get_azure_subscription_id(self, cli_override: Optional[str] = None) -> str:
        """
        Get Azure subscription ID from config.yaml or CLI override.
        
        Args:
            cli_override: Optional CLI argument value to override config
            
        Returns:
            Azure subscription ID
            
        Raises:
            ValueError: If no subscription_id is configured and no CLI override provided
        """
        if cli_override:
            return cli_override
        return self._azure_infra_section().get('subscription_id')

    def get_azure_resource_group(self, cli_override: Optional[str] = None) -> str:
        """
        Get Azure resource group from config.yaml or CLI override.
        
        Args:
            cli_override: Optional CLI argument value to override config
            
        Returns:
            Azure resource group name
            
        Raises:
            ValueError: If no resource_group is configured and no CLI override provided
        """
        if cli_override:
            return cli_override
        return self._azure_infra_section().get('resource_group', 'adme-performance-rg')

    def get_azure_location(self, cli_override: Optional[str] = None) -> str:
        """
        Get Azure location from config.yaml or CLI override.
        
        Args:
            cli_override: Optional CLI argument value to override config
            
        Returns:
            Azure location (defaults to "eastus" if not configured)
        """
        if cli_override:
            return cli_override
        return self._azure_infra_section().get('location', 'eastus')

    def get_azure_load_test_name(self, cli_override: Optional[str] = None) -> Optional[str]:
        """
        Get the name of the Azure Load Test resource to use.

        Resolution order:
            1. Explicit CLI override (``--loadtest-name``).
            2. ``azure_infra.azure_load_test.name`` in system_config.yaml.

        Returns ``None`` if neither source supplies a value so the caller
        can surface a clear error instead of silently defaulting to a
        made-up resource name.
        """
        if cli_override:
            return cli_override
        alt = self._azure_infra_section().get('azure_load_test') or {}
        return alt.get('name')

    def get_allow_resource_creation(self) -> bool:
        """Whether the tool may create the resource group + Azure Load Test
        resource when they don't exist. Controlled by
        ``azure_infra.allow_resource_creation``; defaults to False.
        """
        value = self._azure_infra_section().get('allow_resource_creation', False)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() == 'true'
        return False

    def get_test_name_prefix(self) -> str:
        """
        Get test name prefix for performance tests.
        
        Returns:
            Test name prefix string (e.g., "osdu_perf_test").
        """
        test_settings = self.get_test_settings()
        return test_settings.get('test_name_prefix', 'osdu_perf_test')

    def get_test_run_id_description(self) -> str:
        """
        Get test run ID description for performance tests.

        Returns:
            Test run ID description string (e.g., "Test run for search API").
        """
        test_settings = self.get_test_settings()
        return test_settings.get('test_run_id_description', 'Test run for search API')

    def load_from_config_file(self, config_path: str) -> None:
        """Legacy single-config loader (disabled)."""
        if False:
            _ = config_path
        raise NotImplementedError(
            "Single config parsing is disabled. Use load_from_split_config_files(system_config_path, test_config_path)."
        )

    def load_from_split_config_files(self, system_config_path: str, test_config_path: Optional[str] = None) -> None:
        """Load configuration from system config and test config (explicit or inferred sibling)."""
        system_file = Path(system_config_path)
        test_file = Path(test_config_path) if test_config_path else (system_file.parent / 'test_config.yaml')

        if not system_file.exists():
            raise FileNotFoundError(f"System config file not found: {system_config_path}")
        if not test_file.exists():
            raise FileNotFoundError(f"Test config file not found: {test_file}")

        self.system_config = self._load_yaml_file(system_file)
        self.test_config = self._load_yaml_file(test_file)
        self.config = {**self.system_config, **self.test_config}
        self.logger.info(
            f"Loaded split configuration from system={system_config_path}, test={test_file}"
        )

    def get_available_scenarios(self) -> Dict[str, Any]:
        """Return configured scenarios map from test config."""
        return self.test_config.get('scenarios', {}) or {}

    def set_selected_scenario(self, scenario_name: Optional[str]) -> None:
        """Set selected scenario used for resolving scenario-specific settings."""
        self.selected_scenario = scenario_name

    def validate_scenario(self, scenario: Optional[str | List[str]]) -> str:
        """Validate exactly one scenario value against test_config.yaml and return normalized value."""
        configured = self.get_available_scenarios()
        if not scenario:
            if configured:
                return next(iter(configured.keys()))
            return ''

        if isinstance(scenario, list):
            normalized = [s.strip() for s in scenario if s and s.strip()]
            if len(normalized) != 1:
                raise ValueError("Exactly one --scenario value is supported for this command")
            scenario_name = normalized[0]
        else:
            scenario_name = scenario.strip()

        if ',' in scenario_name:
            raise ValueError(
                "Exactly one --scenario value is supported; comma-separated values are not allowed"
            )
        if configured and scenario_name not in configured:
            raise ValueError(
                f"Invalid scenario: {scenario_name}. Available: {', '.join(configured.keys())}"
            )
        return scenario_name

    def validate_scenarios(self, scenarios: Optional[List[str]]) -> List[str]:
        """Backward-compatible wrapper around single-scenario validation."""
        validated = self.validate_scenario(scenarios)
        return [validated] if validated else []
        
    def get_test_run_name(self, test_name: str) -> str:
        """
        Generate a unique test run name by appending a timestamp to the base test name.
        Args:
            test_name: Base name for the test run
        Returns:
            Unique test run name with timestamp appended
        """

        max_length = 50  # Maximum length for the test run name
        timestamp = datetime.now().strftime('%m%d_%H%M%S')  # Shorter timestamp
        max_base_length = max_length - len(f"{timestamp}")
        return f"{test_name[:max_base_length]}-{timestamp}"

    def get_test_scenario(self, cli_override: Optional[List[str] | str] = None) -> str:
        """
        Get test scenario from config.yaml or CLI override.
        
        Args:
            cli_override: Optional CLI argument value to override config
            
        Returns:
            Test scenario value (defaults to "storage1" if not configured)
        """
        if cli_override:
            return self.validate_scenario(cli_override)

        test_settings = self.get_test_settings()
        configured_scenario = test_settings.get('test_scenario', '')
        if configured_scenario:
            return self.validate_scenario(configured_scenario)
        return ''

    def get_test_metadata(self) -> Dict[str, Any]:
        """Return free-form test-run metadata merged from all sources.

        Precedence (lowest → highest):

        1. ``test_metadata:`` top-level mapping in ``system_config.yaml``.
        2. ``scenarios.<name>.metadata:`` mapping in ``test_config.yaml``.

        Scenario metadata overrides system metadata on key collision.
        """
        metadata: Dict[str, Any] = {}

        system_meta = self.system_config.get('test_metadata', {}) or {}
        if isinstance(system_meta, dict):
            metadata.update({k: v for k, v in system_meta.items() if v is not None})

        scenarios = self.test_config.get('scenarios', {}) or {}
        scenario_name = self.selected_scenario or os.getenv('TEST_SCENARIO')
        if scenario_name and scenario_name in scenarios:
            scenario_meta = (scenarios[scenario_name] or {}).get('metadata', {}) or {}
            if isinstance(scenario_meta, dict):
                metadata.update({k: v for k, v in scenario_meta.items() if v is not None})

        return metadata