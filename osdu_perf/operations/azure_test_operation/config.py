"""Configuration management for Azure Load Test Runner."""

from typing import Dict, Optional
from dataclasses import dataclass, field


@dataclass
class AzureLoadTestConfig:
    """Configuration settings for Azure Load Testing."""
    
    # Azure Resource Configuration
    subscription_id: str
    resource_group_name: str
    load_test_name: str
    location: str = "eastus"
    tags: Dict[str, str] = field(default_factory=lambda: {
        "Environment": "Performance Testing",
        "Service": "OSDU"
    })
    sku: str = "Standard"
    
    # Test Configuration
    version: str = "25.1.23"
    test_runid_name: str = "osdu-perf-test"
    
    # API Configuration
    management_base_url: str = "https://management.azure.com"
    api_version: str = "2024-12-01-preview"
    
    # Data Plane Configuration (set after resource creation)
    data_plane_url: Optional[str] = None
    principal_id: Optional[str] = None
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.subscription_id:
            raise ValueError("subscription_id is required")
        if not self.resource_group_name:
            raise ValueError("resource_group_name is required")
        if not self.load_test_name:
            raise ValueError("load_test_name is required")
    
    def update_data_plane_info(self, data_plane_url: str, principal_id: str):
        """Update data plane information after resource creation."""
        self.data_plane_url = data_plane_url
        self.principal_id = principal_id
    
    def to_dict(self) -> Dict:
        """Convert config to dictionary."""
        return {
            "subscription_id": self.subscription_id,
            "resource_group_name": self.resource_group_name,
            "load_test_name": self.load_test_name,
            "location": self.location,
            "tags": self.tags,
            "sku": self.sku,
            "version": self.version,
            "test_runid_name": self.test_runid_name,
            "api_version": self.api_version,
            "data_plane_url": self.data_plane_url,
            "principal_id": self.principal_id
        }
