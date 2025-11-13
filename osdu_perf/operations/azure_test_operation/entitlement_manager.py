"""Entitlement management for Azure Load Testing with OSDU."""

import logging
import urllib.request
import urllib.error
import json
from typing import Dict, Any, Optional


class UrllibResponse:
    """Compatibility wrapper for urllib responses."""
    
    def __init__(self, status_code: int, content: bytes, headers: Optional[Dict] = None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.text = content.decode('utf-8') if content else ''
    
    def json(self):
        """Parse response content as JSON."""
        return json.loads(self.text) if self.text else {}


class AzureLoadTestEntitlementManager:
    """Manages entitlements for Azure Load Testing with OSDU integration."""
    
    def __init__(
        self,
        credential: Any,
        principal_id: str,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the entitlement manager.
        
        Args:
            credential: Azure credential for authentication
            principal_id: Principal ID of the load test resource
            logger: Logger instance
        """
        self.credential = credential
        self.principal_id = principal_id
        self.logger = logger or logging.getLogger(__name__)
    
    def get_app_id_from_principal_id(self, principal_id: str) -> str:
        """
        Get App ID from Object (principal) ID using Microsoft Graph API.
        
        Args:
            principal_id: The Object (principal) ID
            
        Returns:
            str: The application ID
        """
        try:
            # Use Microsoft Graph API to get service principal details
            self.logger.info(f"Acquiring token for Microsoft Graph...")
            token = self.credential.get_token("https://graph.microsoft.com/")
            token = token.token
            url = f"https://graph.microsoft.com/v1.0/servicePrincipals/{principal_id}"
            
            # Create urllib request for service principal lookup
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", "application/json")
            
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    response_obj = UrllibResponse(response.getcode(), response.read(), dict(response.headers))
            except urllib.error.HTTPError as e:
                error_content = e.read() if hasattr(e, 'read') else b''
                response_obj = UrllibResponse(e.code, error_content, dict(e.headers) if hasattr(e, 'headers') else {})
            
            response = response_obj
            
            if response.status_code == 200:
                service_principal = response.json()
                if 'appId' in service_principal:
                    app_id = service_principal['appId']
                    self.logger.info(f"✅ Resolved app ID: {app_id}")
                    return app_id
                else:
                    self.logger.error(f"No appId found for principal ID '{principal_id}'")
                    raise ValueError(f"No appId found for principal ID '{principal_id}'")
            else:
                self.logger.error(f"Failed to get service principal details: {response.status_code} - {response.text}")
                raise Exception(f"Failed to get service principal details: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Error getting app ID from principal ID '{principal_id}': {e}")
            raise
    
    def setup_load_test_entitlements(
        self,
        load_test_name: str,
        host: str,
        partition: str,
        osdu_adme_token: str
    ) -> bool:
        """
        Set up entitlements for a load test application with OSDU.
        
        This function:
        1. Resolves the app ID from the principal ID
        2. Creates an Entitlement object with OSDU configuration
        3. Creates entitlements for the load test app
        
        Args:
            load_test_name: Name of the load test instance
            host: OSDU host URL (e.g., https://your-osdu-host.com)
            partition: OSDU data partition ID (e.g., opendes)
            osdu_adme_token: Bearer token for OSDU authentication
            
        Returns:
            bool: True if entitlements were set up successfully
        """
        try:
            self.logger.info(f"Setting up entitlements for load test: {load_test_name}")
            
            # Step 1: Get app ID from principal ID
            self.logger.info("Resolving application ID from principal ID...")
            app_id = self.get_app_id_from_principal_id(self.principal_id)
            self.logger.info(f"Resolved app ID: {app_id}")
            
            # Step 2: Import and create Entitlement object
            from ..entitlement import Entitlement
            
            self.logger.info("Creating entitlement manager...")
            entitlement = Entitlement(
                host=host,
                partition=partition,
                load_test_app_id=app_id,
                token=osdu_adme_token
            )
            
            # Step 3: Create entitlements for the load test app
            self.logger.info("Creating entitlements for load test application...")
            entitlement_result = entitlement.create_entitlment_for_load_test_app()
            
            if entitlement_result['success']:
                self.logger.info(f"✅ Successfully set up entitlements for load test '{load_test_name}'")
                self.logger.info(f"   App ID: {app_id}")
                self.logger.info(f"   Partition: {partition}")
                self.logger.info(f"   Result: {entitlement_result['message']}")
                self.logger.info(f"   Groups processed:")
                
                for group_result in entitlement_result['results']:
                    group_name = group_result['group']
                    if group_result['conflict']:
                        self.logger.info(f"     • {group_name} (already existed)")
                    elif group_result['success']:
                        self.logger.info(f"     • {group_name} (newly added)")
                    else:
                        self.logger.warning(f"     • {group_name} (failed: {group_result['message']})")
                        
                return True
            else:
                self.logger.error(f"❌ Failed to set up entitlements for load test '{load_test_name}'")
                self.logger.error(f"   Result: {entitlement_result['message']}")
                for group_result in entitlement_result['results']:
                    if not group_result['success']:
                        self.logger.error(f"   • {group_result['group']}: {group_result['message']}")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ Failed to set up entitlements for load test '{load_test_name}': {e}")
            return False
