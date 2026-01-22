"""Shared test fixtures for osdu_perf tests."""
import pytest
from unittest.mock import Mock, MagicMock
from azure.core.credentials import AccessToken
import time


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for testing."""
    client = Mock()
    client.get = Mock()
    client.post = Mock()
    client.put = Mock()
    client.delete = Mock()
    return client


@pytest.fixture
def mock_locust_environment():
    """Mock Locust environment for testing."""
    env = Mock()
    env.host = "https://test.osdu.com"
    env.parsed_options = Mock()
    env.parsed_options.partition = "test-partition"
    env.parsed_options.appid = "test-app-id"
    return env


@pytest.fixture
def mock_access_token():
    """Mock Azure access token."""
    return AccessToken(token="test-token", expires_on=time.time() + 3600)


@pytest.fixture
def sample_service_data():
    """Sample service discovery data."""
    return {
        "services": [
            {"name": "search", "endpoint": "/api/search/v2"},
            {"name": "storage", "endpoint": "/api/storage/v2"},
            {"name": "schema", "endpoint": "/api/schema-service/v1"}
        ]
    }


@pytest.fixture
def mock_response():
    """Mock HTTP response."""
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"success": True}
    response.text = '{"success": true}'
    response.raise_for_status.return_value = None
    return response