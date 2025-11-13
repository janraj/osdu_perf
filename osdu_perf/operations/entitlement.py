"""
OSDU Entitlement Management Module

This module provides functionality for managing OSDU         url = f"{self.host}/api/entitlements/v2/members/{email}/groups?type=none"
        
        payload = {}
        
        try:
            response = requests.get(url, headers=self.headers, data=payload)
            print(f"Got the user groups: {response.text}")
            print(f"getUserGroupStatusCode: {response.status_code}")
            print(f"For User: {users}")
        except Exception as e:cluding
user management, group operations, and role assignments.
"""

import json
import requests
from typing import Optional


class Entitlement:
    """
    OSDU Entitlement Management Class
    
    Handles user entitlement operations for OSDU including adding users to groups,
    retrieving groups, and managing user group memberships.
    """
    
    def __init__(self, host: str, partition: str, load_test_app_id: str, token: str):
        """
        Initialize the Entitlement manager.
        
        Args:
            host: OSDU host URL (e.g., https://your-osdu-host.com)
            partition: OSDU data partition ID (e.g., opendes)
            load_test_app_id: Azure AD Application ID for OSDU authentication
            token: Bearer token for OSDU authentication
        """
        self.host = host.rstrip('/')  # Remove trailing slash if present
        self.partition = partition
        self.load_test_app_id = load_test_app_id
        self.email = load_test_app_id  # In our case, email and load_test_app_id are the same
        self.role = "MEMBER"  # Default role for user operations
        self.token = token
        
        # Create headers once for all requests
        self.headers = {
            'data-partition-id': self.partition,
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
    
    def adduser(self, users: str) -> dict:
        """
        Add a user to a specific group with a given role.
        
        Args:
            users: Group/user identifier to add the user to
            
        Returns:
            dict: Status information with 'success' (bool), 'status_code' (int), 
                  'message' (str), and 'conflict' (bool) keys
        """
        url = f"{self.host}/api/entitlements/v2/groups/{users}/members"
        
        payload = json.dumps({
            "email": self.email,
            "role": self.role
        })
        
        try:
            response = requests.post(url, headers=self.headers, data=payload)
            
            # Consider both success (2xx) and conflict (409) as successful outcomes
            is_success = (200 <= response.status_code < 300)
            is_conflict = (response.status_code == 409)
            is_overall_success = is_success or is_conflict
            
            if is_conflict:
                message = f"Entitlement already exists for group '{users}' (status: {response.status_code})"
                print(f"✅ {message}")
            elif is_success:
                message = f"Successfully added user to group '{users}' (status: {response.status_code})"
                print(f"✅ {message}")
            else:
                message = f"Failed to add user to group '{users}': {response.status_code} - {response.text}"
                print(f"❌ {message}")
            
            print(f"AddUser result: {response.text}")
            print(f"addUserStatusCode: {response.status_code}")
            print(f"For User: {users}")
            
            return {
                'success': is_overall_success,
                'status_code': response.status_code,
                'message': message,
                'conflict': is_conflict,
                'response_text': response.text
            }
            
        except Exception as e:
            error_message = f"Error adding user to group '{users}': {e}"
            print(f"❌ {error_message}")
            return {
                'success': False,
                'status_code': 0,
                'message': error_message,
                'conflict': False,
                'response_text': str(e)
            }
    
    def getgroups(self, users: str, email: str, role: str) -> None:
        """
        Retrieve all available groups from the OSDU entitlement service.
        
        Args:
            users: User identifier (for logging purposes)
            email: Email address (for logging purposes)
            role: Role (for logging purposes)
        """
        url = f"{self.host}/api/entitlements/v2/groups"
        
        payload = {}
        
        try:
            response = requests.get(url, headers=self.headers, data=payload)
            print(f"Got the user groups: {response.text}")
            print(f"getGroupsStatusCode: {response.status_code}")
            print(f"For User: {users}")
        except Exception as e:
            print(f"Error getting groups: {e}")
    
    def getuserGroup(self, users: str, email: str, role: str) -> None:
        """
        Get groups that a specific user belongs to.
        
        Args:
            users: User identifier (for logging purposes)
            email: Email address of the user to query
            role: Role (for logging purposes)
        """
        url = f"{self.host}/api/entitlements/v2/members/{email}/groups?type=none"
        
        payload = {}
        headers = {
            'data-partition-id': self.partition,
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
        
        try:
            response = requests.get(url, headers=headers, data=payload)
            print(f"Got the user groups: {response.text}")
            print(f"getUserGroupStatusCode: {response.status_code}")
            print(f"For User: {users}")
        except Exception as e:
            print(f"Error getting user groups: {e}")

    def create_entitlment_for_load_test_app(self) -> dict:
        """
        Create entitlement for the load test application by adding it to specified groups.
        
        Returns:
            dict: Overall status with 'success' (bool), 'results' (list), and 'message' (str)
        """
        groups = [
            f"users@{self.partition}.dataservices.energy",
            f"users.datalake.editors@{self.partition}.dataservices.energy",
            f"users.datalake.admins@{self.partition}.dataservices.energy"
        ]
        
        results = []
        overall_success = True
        
        for group in groups:
            result = self.adduser(group)
            results.append({
                'group': group,
                **result
            })
            # If any group addition fails (not success and not conflict), mark overall as failed
            if not result['success']:
                overall_success = False
        
        # Create summary message
        successful_groups = [r['group'] for r in results if r['success']]
        failed_groups = [r['group'] for r in results if not r['success']]
        conflict_groups = [r['group'] for r in results if r['conflict']]
        
        message_parts = []
        if successful_groups:
            message_parts.append(f"Successfully processed {len(successful_groups)} group(s)")
        if conflict_groups:
            message_parts.append(f"{len(conflict_groups)} group(s) already existed")
        if failed_groups:
            message_parts.append(f"{len(failed_groups)} group(s) failed")
        
        message = "; ".join(message_parts) if message_parts else "No groups processed"
        
        return {
            'success': overall_success,
            'results': results,
            'message': message,
            'processed_groups': len(results),
            'successful_groups': len([r for r in results if r['success']]),
            'conflict_groups': len(conflict_groups),
            'failed_groups': len(failed_groups)
        }