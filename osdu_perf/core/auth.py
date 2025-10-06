
import requests
import logging
import time
from typing import Optional, Dict, Any
from azure.identity import AzureCliCredential, DefaultAzureCredential, ManagedIdentityCredential
from azure.core.exceptions import ClientAuthenticationError
from azure.core.credentials import AccessToken

class AzureTokenManager:
    """
    Production-quality Azure token manager for authentication with various Azure services.
    
    Supports multiple authentication methods:
    - Azure CLI (for local development)
    - Managed Identity (for Azure environments)
    - Default Azure Credential (fallback)
    """
    
    def __init__(self, client_id: Optional[str] = None, use_managed_identity: bool = False):
        """
        Initialize the Azure Token Manager.
        
        Args:
            client_id: Azure AD App ID for which to obtain tokens
            use_managed_identity: Whether to use managed identity authentication
        """
        self.client_id = client_id
        self.use_managed_identity = use_managed_identity
        self.logger = logging.getLogger(__name__)
        self._credential = None
        self._cached_tokens: Dict[str, AccessToken] = {}
        
        # Initialize credential based on configuration
        self.logger.info(f"Initialized with Managed Identity credential scope is {client_id} {use_managed_identity}") 
        #self._initialize_credential()  Locustwhen we run firstnotable to retrive env so commenting logic now
    
    def _initialize_credential(self) -> None:
        """Initialize the appropriate Azure credential based on configuration."""
        try:
            if self.use_managed_identity:
                self._credential = ManagedIdentityCredential()
                self.logger.info(f"Initialized with Managed Identity credential ")
            else:
                # Try Azure CLI first, fallback to DefaultAzureCredential
                try:
                    self._credential = AzureCliCredential()
                    self.logger.info("Initialized with Azure CLI credential")
                except Exception:
                    self._credential = DefaultAzureCredential()
                    self.logger.info("Initialized with Default Azure credential")
                    
        except Exception as e:
            self.logger.error(f"Failed to initialize Azure credential: {e}")
            raise
    
    def get_access_token(self, scope: Optional[str] = None) -> Optional[str]:
        """
        Get an access token for the specified scope.
        
        Args:
            scope: The scope/resource for which to obtain the token.
                  If not provided, uses the client_id to construct api://{client_id}/.default
        
        Returns:
            Access token string or None if authentication fails
        """
        
        if not self.client_id:
            self.logger.error("Either scope or client_id must be provided")
            return None
        scope = self.client_id
        
        try:
            # Check if we have a cached valid token
            cached_token = self._get_cached_token(scope)
            if cached_token:
                return cached_token.token
            
            # Get new token
            try:
                self._credential = ManagedIdentityCredential()
                token = self._credential.get_token(scope)
            except Exception as e1:
                self.logger.warning(f"ManagedIdentityCredential failed: {e1}. Trying AzureCliCredential.")
                try:
                    self._credential = AzureCliCredential()
                    token = self._credential.get_token(scope)
                except Exception as e2:
                    self.logger.warning(f"AzureCliCredential failed: {e2}. Trying DefaultAzureCredential.")
                    self._credential = DefaultAzureCredential()
                    token = self._credential.get_token(scope)
            # Cache the token
            self._cached_tokens[scope] = token
            
            self.logger.info(f"Successfully obtained access token for scope: {scope}")
            self.logger.debug(f"Token expires at: {time.ctime(token.expires_on)}")
            
            return token.token
            
        except ClientAuthenticationError as e:
            self.logger.error(f"Authentication failed for scope '{scope}': {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error obtaining token for scope '{scope}': {e}")
            return None
    
    def _get_cached_token(self, scope: str) -> Optional[AccessToken]:
        """
        Get cached token if it exists and is still valid.
        
        Args:
            scope: The scope for which to check cached token
            
        Returns:
            AccessToken if valid cached token exists, None otherwise
        """
        if scope not in self._cached_tokens:
            return None
        
        token = self._cached_tokens[scope]
        
        # Check if token is still valid (with 5-minute buffer)
        current_time = time.time()
        if token.expires_on - current_time > 300:  # 5 minutes buffer
            self.logger.debug(f"Using cached token for scope: {scope}")
            return token
        
        # Token expired or about to expire, remove from cache
        del self._cached_tokens[scope]
        self.logger.debug(f"Cached token expired for scope: {scope}")
        return None
    
    def get_auth_headers(self, scope: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Get authorization headers with Bearer token.
        
        Args:
            scope: The scope for which to obtain the token
            
        Returns:
            Dictionary with Authorization header or None if token acquisition fails
        """
        token = self.get_access_token(scope)
        if not token:
            return None
        
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def validate_token_access(self, scope: Optional[str] = None) -> bool:
        """
        Validate that we can obtain a token for the specified scope.
        
        Args:
            scope: The scope to validate access for
            
        Returns:
            True if token can be obtained, False otherwise
        """
        token = self.get_access_token(scope)
        return token is not None
    
    def get_token_info(self, scope: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get information about the token without exposing the token value.
        
        Args:
            scope: The scope for which to get token info
            
        Returns:
            Dictionary with token information (without token value)
        """
        if not scope:
            if not self.client_id:
                return None
            scope = f"api://{self.client_id}/.default"
        
        try:
            token = self._credential.get_token(scope)
            
            expires_in_seconds = max(0, token.expires_on - time.time())
            expires_in_minutes = expires_in_seconds / 60
            
            return {
                "scope": scope,
                "expires_in_seconds": int(expires_in_seconds),
                "expires_in_minutes": round(expires_in_minutes, 2),
                "expires_at": time.ctime(token.expires_on),
                "is_valid": expires_in_seconds > 300,  # Valid if more than 5 minutes left
                "token_length": len(token.token),
                "credential_type": type(self._credential).__name__
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get token info: {e}")
            return None
    
    def clear_token_cache(self) -> None:
        """Clear all cached tokens."""
        self._cached_tokens.clear()
        self.logger.info("Token cache cleared")


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    token_manager = AzureTokenManager(client_id="2f59abbc-7b40-4d0e-91b2-22ca3084bc84", use_managed_identity=False)
    token = token_manager.get_access_token("https://management.azure.com/.default") 
    print(f"Access Token: {token}")
