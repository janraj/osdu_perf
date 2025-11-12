import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict
from datetime import datetime, timezone
import pytz
from azure.identity import AzureCliCredential, ManagedIdentityCredential


class AuthenticationStrategy(ABC):
    """Abstract base class for authentication strategies."""
    
    @abstractmethod
    def get_token(self, scope: str) -> str:
        """Get access token for the specified scope."""
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """Get the name of this authentication strategy."""
        pass


class AzureCliStrategy(AuthenticationStrategy):
    """Authentication strategy using Azure CLI credentials."""
    
    def __init__(self):
        self.credential = AzureCliCredential()
        self.logger = logging.getLogger(__name__)
        self._cached_tokens = {}
    
    
    def get_token(self, scope: str) -> str:
        """Get token using Azure CLI credentials."""
        self.logger.info(f"Getting CLI token for scope: {scope}")
        token = self.get_cached_token(scope)
        if token:
            self.logger.info(f"Using cached token for scope: {scope}")
            return token
        try:
            token = self.credential.get_token(scope)

            if token:
                self._cached_tokens[scope] = token.token
                self.logger.info(f"Obtained new token for scope: {scope} and token is = {token.token}")
                
                # Convert expiry time to IST and log it
                if hasattr(token, 'expires_on'):
                    # expires_on is a Unix timestamp
                    expiry_utc = datetime.fromtimestamp(token.expires_on, tz=timezone.utc)
                    ist_timezone = pytz.timezone('Asia/Kolkata')
                    expiry_ist = expiry_utc.astimezone(ist_timezone)
                    self.logger.info(f"🔑 Token expires at: {expiry_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                
            return token.token
        except Exception as e:
            self.logger.error(f"Error obtaining token from Azure CLI: {e}")
            raise
    
    def get_cached_token(self, scope: str) -> str:
        """Return cached token if still valid (>5 minutes before expiry)."""
        token = self._cached_tokens.get(scope, None)
        if not token:
            return None
        return token
    
    def get_strategy_name(self) -> str:
        return "Azure CLI"


class ManagedIdentityStrategy(AuthenticationStrategy):
    """Authentication strategy using Managed Identity credentials."""
    
    def __init__(self, client_id: Optional[str] = None):
        self.credential = ManagedIdentityCredential(client_id=client_id)
        self.client_id = client_id
        self.logger = logging.getLogger(__name__)
        self._cached_tokens = {}
    
    def get_token(self, scope: str) -> str:
        """Get token using Managed Identity credentials."""
        # Use client_id as scope if provided, otherwise use the provided scope
        actual_scope = self.client_id if self.client_id else scope
        actual_scope = f"api://{actual_scope}/.default"
        self.logger.info(f"Getting Managed Identity token for scope: {actual_scope}")
        token = self.get_cached_token(actual_scope)

        try:
            if token:
                self.logger.info(f"Using cached token for scope: {actual_scope}")
                return token
            
            token = self.credential.get_token(actual_scope)
            if token:   
                self._cached_tokens[actual_scope] = token.token
            return token.token
        except Exception as e:
            self.logger.error(f"Error obtaining token from Managed Identity: {e}")
            raise
    
    def get_cached_token(self, scope: str) -> str:
        """Return cached token if still valid (>5 minutes before expiry)."""
        token = self._cached_tokens.get(scope, None)
        if not token:
            return None
        return token
       
    
    def get_strategy_name(self) -> str:
        return "Managed Identity"

class InputTokenStrategy(AuthenticationStrategy):
    """Authentication strategy using Azure CLI credentials."""
    
    def __init__(self, token):
        self.logger = logging.getLogger(__name__)
        self.token = token
    
    
    def get_token(self, scope: str) -> str:
        """Get token using Azure input token credentials."""
        self.logger.info(f"Getting input token for scope: {scope}")
        return self.token
    
    def get_strategy_name(self) -> str:
        return "Input Token"
    
class AzureTokenManager:
    """
    Simplified Azure token manager using Strategy Pattern.
    
    Supports two authentication methods:
    - Azure CLI (for local development)  
    - Managed Identity (for Azure environments)
    """
    
    def __init__(self, client_id: Optional[str] = None, use_managed_identity: bool = False, token: Optional[str] = None):
        """
        Initialize the Azure Token Manager with a specific strategy.
        
        Args:
            client_id: Azure AD App ID for which to obtain tokens
            use_managed_identity: Whether to use managed identity authentication
        """
        self.client_id = client_id
        self.logger = logging.getLogger(__name__)
        
        # Select strategy based on configuration
        if use_managed_identity:
            self.strategy = ManagedIdentityStrategy(client_id)
        else:
            self.strategy = AzureCliStrategy()
        self.token = token
        
        self.logger.info(f"Initialized with {self.strategy.get_strategy_name()} strategy")
    
    def az_account_get_access_token(self) -> str:
        """Get access token using Azure CLI strategy with management scope."""
        # Force CLI strategy for this method
        cli_strategy = AzureCliStrategy()
        scope = "https://management.core.windows.net/.default"
        return cli_strategy.get_token(scope)
    
    def mi_get_access_token(self, scope: Optional[str] = None) -> str:
        """Get access token using Managed Identity strategy."""
        # Force Managed Identity strategy for this method
        mi_strategy = ManagedIdentityStrategy(self.client_id)
        actual_scope = scope or self.client_id
        return mi_strategy.get_token(actual_scope)
    
    def get_access_token(self, scope: str) -> str:
        """Get access token using the selected strategy."""
        if self.token:
            input_token_strategy = InputTokenStrategy(self.token)
            return input_token_strategy.get_token(scope)
        return self.strategy.get_token(scope)