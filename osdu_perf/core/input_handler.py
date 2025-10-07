import os
import logging

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
        else:
            self.logger.info(f"Host: {environment.host} Partition: {environment.parsed_options.partition} App ID: {environment.parsed_options.appid}")
            self.partition = environment.parsed_options.partition
            self.base_url = environment.host
            self.app_id = environment.parsed_options.appid
        
        
        
        self.header = self.prepare_headers()
    
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
