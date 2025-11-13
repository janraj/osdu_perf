"""
Test cases for OSDU Entitlement Management Module.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from osdu_perf.operations.entitlement import Entitlement


class TestEntitlement:
    """Test cases for Entitlement class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.host = "https://test.osdu.com"
        self.partition = "opendes"
        self.load_test_app_id = "test-app-id"
        self.token = "test-token"
        
        self.entitlement = Entitlement(
            host=self.host,
            partition=self.partition,
            load_test_app_id=self.load_test_app_id,
            token=self.token
        )
    
    def test_initialization(self):
        """Test Entitlement class initialization."""
        assert self.entitlement.host == self.host
        assert self.entitlement.partition == self.partition
        assert self.entitlement.load_test_app_id == self.load_test_app_id
        assert self.entitlement.email == self.load_test_app_id
        assert self.entitlement.role == "MEMBER"
        assert self.entitlement.token == self.token
    
    def test_initialization_removes_trailing_slash(self):
        """Test that trailing slash is removed from host."""
        host_with_slash = "https://test.osdu.com/"
        entitlement = Entitlement(host_with_slash, self.partition, self.load_test_app_id, self.token)
        assert entitlement.host == "https://test.osdu.com"
    
    def test_headers_configuration(self):
        """Test that headers are properly configured."""
        expected_headers = {
            'data-partition-id': self.partition,
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
        assert self.entitlement.headers == expected_headers
    
    @patch('osdu_perf.operations.entitlement.requests.post')
    def test_adduser_success(self, mock_post):
        """Test successful user addition to group."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "success"}'
        mock_post.return_value = mock_response
        
        group_name = "test-group"
        result = self.entitlement.adduser(group_name)
        
        # Verify request was made correctly
        expected_url = f"{self.host}/api/entitlements/v2/groups/{group_name}/members"
        expected_payload = json.dumps({
            "email": self.load_test_app_id,
            "role": "MEMBER"
        })
        
        mock_post.assert_called_once_with(
            expected_url,
            headers=self.entitlement.headers,
            data=expected_payload
        )
        
        # Verify result
        assert result['success'] is True
        assert result['status_code'] == 200
        assert result['conflict'] is False
        assert "Successfully added user" in result['message']
        assert result['response_text'] == '{"status": "success"}'
    
    @patch('osdu_perf.operations.entitlement.requests.post')
    def test_adduser_conflict(self, mock_post):
        """Test user addition with conflict (409 status)."""
        # Setup mock response for conflict
        mock_response = Mock()
        mock_response.status_code = 409
        mock_response.text = '{"error": "User already exists"}'
        mock_post.return_value = mock_response
        
        group_name = "existing-group"
        result = self.entitlement.adduser(group_name)
        
        # Verify result treats conflict as success
        assert result['success'] is True
        assert result['status_code'] == 409
        assert result['conflict'] is True
        assert "Entitlement already exists" in result['message']
        assert result['response_text'] == '{"error": "User already exists"}'
    
    @patch('osdu_perf.operations.entitlement.requests.post')
    def test_adduser_failure(self, mock_post):
        """Test user addition failure."""
        # Setup mock response for failure
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = '{"error": "Internal server error"}'
        mock_post.return_value = mock_response
        
        group_name = "error-group"
        result = self.entitlement.adduser(group_name)
        
        # Verify result
        assert result['success'] is False
        assert result['status_code'] == 500
        assert result['conflict'] is False
        assert "Failed to add user" in result['message']
        assert result['response_text'] == '{"error": "Internal server error"}'
    
    @patch('osdu_perf.operations.entitlement.requests.post')
    def test_adduser_exception(self, mock_post):
        """Test user addition with exception."""
        # Setup mock to raise exception
        mock_post.side_effect = Exception("Network error")
        
        group_name = "exception-group"
        result = self.entitlement.adduser(group_name)
        
        # Verify result
        assert result['success'] is False
        assert result['status_code'] == 0
        assert result['conflict'] is False
        assert "Error adding user" in result['message']
        assert "Network error" in result['response_text']
    
    @patch('osdu_perf.operations.entitlement.requests.get')
    def test_getgroups_success(self, mock_get, capsys):
        """Test successful groups retrieval."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"groups": ["group1", "group2"]}'
        mock_get.return_value = mock_response
        
        users = "test-user"
        email = "test@example.com"
        role = "MEMBER"
        
        self.entitlement.getgroups(users, email, role)
        
        # Verify request was made correctly
        expected_url = f"{self.host}/api/entitlements/v2/groups"
        mock_get.assert_called_once_with(
            expected_url,
            headers=self.entitlement.headers,
            data={}
        )
        
        # Verify console output
        captured = capsys.readouterr()
        assert '{"groups": ["group1", "group2"]}' in captured.out
        assert "getGroupsStatusCode: 200" in captured.out
        assert "For User: test-user" in captured.out
    
    @patch('osdu_perf.operations.entitlement.requests.get')
    def test_getgroups_exception(self, mock_get, capsys):
        """Test groups retrieval with exception."""
        # Setup mock to raise exception
        mock_get.side_effect = Exception("Connection error")
        
        self.entitlement.getgroups("test-user", "test@example.com", "MEMBER")
        
        # Verify error message
        captured = capsys.readouterr()
        assert "Error getting groups: Connection error" in captured.out
    
    @patch('osdu_perf.operations.entitlement.requests.get')
    def test_getuserGroup_success(self, mock_get, capsys):
        """Test successful user group retrieval."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"userGroups": ["group1", "group2"]}'
        mock_get.return_value = mock_response
        
        users = "test-user"
        email = "test@example.com"
        role = "MEMBER"
        
        self.entitlement.getuserGroup(users, email, role)
        
        # Verify request was made correctly
        expected_url = f"{self.host}/api/entitlements/v2/members/{email}/groups?type=none"
        expected_headers = {
            'data-partition-id': self.partition,
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
        
        mock_get.assert_called_once_with(
            expected_url,
            headers=expected_headers,
            data={}
        )
        
        # Verify console output
        captured = capsys.readouterr()
        assert '{"userGroups": ["group1", "group2"]}' in captured.out
        assert "getUserGroupStatusCode: 200" in captured.out
        assert "For User: test-user" in captured.out
    
    @patch('osdu_perf.operations.entitlement.requests.get')
    def test_getuserGroup_exception(self, mock_get, capsys):
        """Test user group retrieval with exception."""
        # Setup mock to raise exception
        mock_get.side_effect = Exception("Timeout error")
        
        self.entitlement.getuserGroup("test-user", "test@example.com", "MEMBER")
        
        # Verify error message
        captured = capsys.readouterr()
        assert "Error getting user groups: Timeout error" in captured.out
    
    @patch.object(Entitlement, 'adduser')
    def test_create_entitlement_for_load_test_app_all_success(self, mock_adduser):
        """Test entitlement creation with all groups successful."""
        # Setup mock to return success for all groups
        mock_adduser.return_value = {
            'success': True,
            'status_code': 200,
            'message': 'Success',
            'conflict': False,
            'response_text': 'OK'
        }
        
        result = self.entitlement.create_entitlment_for_load_test_app()
        
        # Verify all three groups were processed
        assert mock_adduser.call_count == 3
        expected_groups = [
            f"users@{self.partition}.dataservices.energy",
            f"users.datalake.editors@{self.partition}.dataservices.energy",
            f"users.datalake.admins@{self.partition}.dataservices.energy"
        ]
        
        # Verify calls were made for each group
        for i, call in enumerate(mock_adduser.call_args_list):
            assert call[0][0] == expected_groups[i]
        
        # Verify result
        assert result['success'] is True
        assert result['processed_groups'] == 3
        assert result['successful_groups'] == 3
        assert result['conflict_groups'] == 0
        assert result['failed_groups'] == 0
        assert "Successfully processed 3 group(s)" in result['message']
        assert len(result['results']) == 3
    
    @patch.object(Entitlement, 'adduser')
    def test_create_entitlement_for_load_test_app_with_conflicts(self, mock_adduser):
        """Test entitlement creation with some conflicts."""
        # Setup mock to return different responses
        responses = [
            {'success': True, 'status_code': 200, 'message': 'Success', 'conflict': False, 'response_text': 'OK'},
            {'success': True, 'status_code': 409, 'message': 'Conflict', 'conflict': True, 'response_text': 'Exists'},
            {'success': True, 'status_code': 201, 'message': 'Created', 'conflict': False, 'response_text': 'Created'}
        ]
        mock_adduser.side_effect = responses
        
        result = self.entitlement.create_entitlment_for_load_test_app()
        
        # Verify result
        assert result['success'] is True
        assert result['processed_groups'] == 3
        assert result['successful_groups'] == 3
        assert result['conflict_groups'] == 1
        assert result['failed_groups'] == 0
        assert "Successfully processed 3 group(s)" in result['message']
        assert "1 group(s) already existed" in result['message']
    
    @patch.object(Entitlement, 'adduser')
    def test_create_entitlement_for_load_test_app_with_failures(self, mock_adduser):
        """Test entitlement creation with some failures."""
        # Setup mock to return mixed responses including failures
        responses = [
            {'success': True, 'status_code': 200, 'message': 'Success', 'conflict': False, 'response_text': 'OK'},
            {'success': False, 'status_code': 500, 'message': 'Error', 'conflict': False, 'response_text': 'Error'},
            {'success': True, 'status_code': 409, 'message': 'Conflict', 'conflict': True, 'response_text': 'Exists'}
        ]
        mock_adduser.side_effect = responses
        
        result = self.entitlement.create_entitlment_for_load_test_app()
        
        # Verify result
        assert result['success'] is False  # Overall failure due to one failed group
        assert result['processed_groups'] == 3
        assert result['successful_groups'] == 2
        assert result['conflict_groups'] == 1
        assert result['failed_groups'] == 1
        assert "Successfully processed 2 group(s)" in result['message']
        assert "1 group(s) already existed" in result['message']
        assert "1 group(s) failed" in result['message']
    
    @patch.object(Entitlement, 'adduser')
    def test_create_entitlement_for_load_test_app_all_failures(self, mock_adduser):
        """Test entitlement creation with all failures."""
        # Setup mock to return failure for all groups
        mock_adduser.return_value = {
            'success': False,
            'status_code': 500,
            'message': 'Server error',
            'conflict': False,
            'response_text': 'Internal server error'
        }
        
        result = self.entitlement.create_entitlment_for_load_test_app()
        
        # Verify result
        assert result['success'] is False
        assert result['processed_groups'] == 3
        assert result['successful_groups'] == 0
        assert result['conflict_groups'] == 0
        assert result['failed_groups'] == 3
        assert "3 group(s) failed" in result['message']
    
    def test_entitlement_groups_list(self):
        """Test that the correct groups are used for entitlement creation."""
        with patch.object(self.entitlement, 'adduser') as mock_adduser:
            mock_adduser.return_value = {
                'success': True, 'status_code': 200, 'message': 'Success', 
                'conflict': False, 'response_text': 'OK'
            }
            
            self.entitlement.create_entitlment_for_load_test_app()
            
            # Verify the correct groups were called
            expected_groups = [
                f"users@{self.partition}.dataservices.energy",
                f"users.datalake.editors@{self.partition}.dataservices.energy",
                f"users.datalake.admins@{self.partition}.dataservices.energy"
            ]
            
            assert mock_adduser.call_count == 3
            called_groups = [call[0][0] for call in mock_adduser.call_args_list]
            assert called_groups == expected_groups


class TestEntitlementStatusCodes:
    """Test entitlement status code handling."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.entitlement = Entitlement(
            host="https://test.osdu.com",
            partition="opendes",
            load_test_app_id="test-app-id",
            token="test-token"
        )
    
    @patch('osdu_perf.operations.entitlement.requests.post')
    def test_adduser_status_codes_success_range(self, mock_post):
        """Test that 2xx status codes are treated as success."""
        success_codes = [200, 201, 202, 204]
        
        for status_code in success_codes:
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_response.text = f'Status: {status_code}'
            mock_post.return_value = mock_response
            
            result = self.entitlement.adduser("test-group")
            
            assert result['success'] is True
            assert result['status_code'] == status_code
            assert result['conflict'] is False
            assert "Successfully added user" in result['message']
    
    @patch('osdu_perf.operations.entitlement.requests.post')
    def test_adduser_status_codes_client_errors(self, mock_post):
        """Test that 4xx status codes (except 409) are treated as failures."""
        error_codes = [400, 401, 403, 404, 422]
        
        for status_code in error_codes:
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_response.text = f'Error: {status_code}'
            mock_post.return_value = mock_response
            
            result = self.entitlement.adduser("test-group")
            
            assert result['success'] is False
            assert result['status_code'] == status_code
            assert result['conflict'] is False
            assert "Failed to add user" in result['message']
    
    @patch('osdu_perf.operations.entitlement.requests.post')
    def test_adduser_status_codes_server_errors(self, mock_post):
        """Test that 5xx status codes are treated as failures."""
        error_codes = [500, 502, 503, 504]
        
        for status_code in error_codes:
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_response.text = f'Server Error: {status_code}'
            mock_post.return_value = mock_response
            
            result = self.entitlement.adduser("test-group")
            
            assert result['success'] is False
            assert result['status_code'] == status_code
            assert result['conflict'] is False
            assert "Failed to add user" in result['message']


class TestEntitlementEdgeCases:
    """Test edge cases and error conditions."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.entitlement = Entitlement(
            host="https://test.osdu.com",
            partition="opendes", 
            load_test_app_id="test-app-id",
            token="test-token"
        )
    
    def test_initialization_with_empty_values(self):
        """Test initialization with empty values."""
        entitlement = Entitlement("", "", "", "")
        assert entitlement.host == ""
        assert entitlement.partition == ""
        assert entitlement.load_test_app_id == ""
        assert entitlement.email == ""
        assert entitlement.token == ""
        assert entitlement.role == "MEMBER"
    
    def test_initialization_with_none_values(self):
        """Test initialization with None values."""
        with pytest.raises(AttributeError):
            # This should fail because None.rstrip() will raise AttributeError
            Entitlement(None, "partition", "app_id", "token")
    
    @patch('osdu_perf.operations.entitlement.requests.post')
    def test_adduser_with_special_characters(self, mock_post):
        """Test adduser with special characters in group name."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'OK'
        mock_post.return_value = mock_response
        
        special_group = "test@group.with-special_chars"
        result = self.entitlement.adduser(special_group)
        
        # Verify URL was built correctly
        expected_url = f"{self.entitlement.host}/api/entitlements/v2/groups/{special_group}/members"
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == expected_url
        assert result['success'] is True
    
    def test_headers_immutability(self):
        """Test that headers are correctly set and don't change unexpectedly."""
        original_headers = self.entitlement.headers.copy()
        
        # Modify the headers externally
        self.entitlement.headers['new-header'] = 'new-value'
        
        # The headers should now be different
        assert self.entitlement.headers != original_headers
        assert 'new-header' in self.entitlement.headers