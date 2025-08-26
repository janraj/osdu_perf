import os

from .auth import AzureTokenManager


class InputHandler:
    def __init__(self, environment):

        print(f"[Input Handler] Host: {environment.host} Partition: {environment.parsed_options.partition}  App ID: {environment.parsed_options.appid}")

        self.partition = environment.parsed_options.partition
        self.base_url = environment.host
        self.app_id = environment.parsed_options.appid
        self.header = self.prepare_headers()
    
    def prepare_headers(self):
        """
        Prepare headers for the HTTP client.
        
        Returns:
            dict: Headers to be used in HTTP requests.
        """
        token_manager = AzureTokenManager(client_id=self.app_id, use_managed_identity=False)
        token = token_manager.get_access_token("https://management.azure.com/.default") 

        #token = self.client.get_access_token(scope=f"api://{self.app_id}/.default")
        headers = {
            "Content-Type": "application/json",
            "x-data-partition-id": self.partition,
            "x-correlation-id": self.app_id,
            "Authorization": f"Bearer {token}"
        }
        return headers
