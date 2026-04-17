import json
import logging
import subprocess
from abc import ABC, abstractmethod
from typing import Optional
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

    # Class-level cache so all user/InputHandler instances share the same
    # token for a given scope instead of shelling out per user.
    _shared_cached_tokens: dict = {}

    def __init__(self):
        self.credential = AzureCliCredential()
        self.logger = logging.getLogger(__name__)
        self._cached_tokens = AzureCliStrategy._shared_cached_tokens
        self.az_commands = ['az', 'az.exe', 'az.cmd']

    def get_token_v1(self, scope: str = None) -> str:
        """Get token by shelling out to ``az account get-access-token``.

        This mirrors what a user would run manually:
            az account get-access-token --resource <appId>

        The ``scope`` may be either a bare app id / resource URI (e.g.
        ``api://<appId>``) or a ``.default`` scope (e.g. ``api://<appId>/.default``).
        We normalize it and pass ``--scope`` when it looks like a scope and
        ``--resource`` otherwise.
        """
        self.logger.info(f"Getting CLI token via 'az account get-access-token' for scope: {scope}")

        cmd_tail = []
        if scope:
            if scope.endswith('/.default') or scope.startswith('https://') or '//' in scope:
                cmd_tail = ['--scope', scope]
            else:
                # Treat as a resource (app id or api:// uri)
                cmd_tail = ['--resource', scope]

        result = None
        for az_cmd in self.az_commands:
            try:
                result = subprocess.run(
                    [az_cmd, 'account', 'get-access-token', *cmd_tail],
                    capture_output=True, text=True, check=True, shell=True,
                )
                break
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                self.logger.debug(f"'{az_cmd}' attempt failed: {e}")
                continue

        if result is None:
            raise RuntimeError(
                "Azure CLI not found or 'az account get-access-token' failed. "
                "Please ensure Azure CLI is installed, in PATH, and that you are logged in via 'az login'."
            )
        if result.returncode != 0:
            raise RuntimeError(
                f"az account get-access-token failed (code {result.returncode}): {result.stderr.strip()}"
            )

        token_info = json.loads(result.stdout)
        access_token = token_info['accessToken']
        self.logger.info("✅ Successfully retrieved access token via Azure CLI")
        return access_token
    
    def get_token(self, scope: str) -> str:
        """Get token using Azure CLI credentials.

        We intentionally shell out to ``az account get-access-token --resource <appId>``
        instead of using ``AzureCliCredential.get_token`` because the SDK call
        passes the scope as-is (``api://<appId>/.default``), which results in a
        token with ``aud = "api://<appId>"``. OSDU services expect the bare app
        id (``aud = "<appId>"``) that ``--resource <appId>`` produces.
        """
        self.logger.info(f"Getting CLI token for scope : {scope}")
        token = self.get_cached_token(scope)
        if token:
            self.logger.info(f"Using cached token for scope: {scope}")
            return token

        # Normalize scope to a bare resource / app id for --resource.
        resource = scope or ""
        if resource.endswith('/.default'):
            resource = resource[: -len('/.default')]
        if resource.startswith('api://'):
            resource = resource[len('api://'):]

        try:
            token = self.get_token_v1(resource)
            if token:
                self._cached_tokens[scope] = token
                self.logger.info(f"Obtained new token for scope: {scope}")
            return token
        except Exception as e:
            self.logger.error(f"Error obtaining token via Azure CLI for resource '{resource}': {e}")
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

    _shared_cached_tokens: dict = {}

    def __init__(self, client_id: Optional[str] = None):
        self.credential = ManagedIdentityCredential(client_id=client_id)
        self.client_id = client_id
        self.logger = logging.getLogger(__name__)
        self._cached_tokens = ManagedIdentityStrategy._shared_cached_tokens
    
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
        scope = "https://management.operations.windows.net/.default"
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