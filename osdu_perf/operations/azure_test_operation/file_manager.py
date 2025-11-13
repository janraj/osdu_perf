"""File management for Azure Load Testing - handles file uploads and operations."""

import logging
import os
import glob
from typing import List, Dict, Any, Optional
from pathlib import Path
from azure.developer.loadtesting import LoadTestAdministrationClient


class AzureLoadTestFileManager:
    """Manages file uploads and operations for Azure Load Testing."""
    
    def __init__(
        self,
        loadtest_admin_client: LoadTestAdministrationClient,
        api_version: str = "2024-12-01-preview",
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the file manager.
        
        Args:
            loadtest_admin_client: Azure Load Test Administration client for file operations
            api_version: API version to use
            logger: Logger instance
        """
        self.loadtest_admin_client = loadtest_admin_client
        self.api_version = api_version
        self.logger = logger or logging.getLogger(__name__)
    
    def upload_files_for_test(
        self,
        test_name: str,
        test_files: List[Path]
    ) -> List[Dict[str, Any]]:
        """
        Upload test files to Azure Load Testing using Data Plane API.
        
        Args:
            test_name: Name of the test 
            test_files: List of test files to upload
            
        Returns:
            List[Dict[str, Any]]: List of uploaded file information
        """
        uploaded_files = []
        self.logger.info(f"Uploading {len(test_files)} files to test '{test_name}'...")
        
        try:
            for file_path in test_files:
                if not file_path.exists():
                    self.logger.warning(f"File does not exist: {file_path}")
                    continue

                self.logger.info(f"Uploading file: {file_path.name}")

                # Determine file type
                # JMX_FILE: Main test scripts (locustfile.py)
                # ADDITIONAL_ARTIFACTS: Supporting files (requirements.txt, utilities, perf.*test.py)
                if file_path.name.lower() == 'locustfile.py':
                    file_type = "JMX_FILE"
                else:
                    file_type = "ADDITIONAL_ARTIFACTS"
                
                # Upload file
                with open(file_path, 'rb') as file_content:
                    result = self.loadtest_admin_client.begin_upload_test_file(
                        test_id=test_name,
                        file_name=file_path.name,
                        file_type=file_type,
                        body=file_content
                    ).result()  # Wait for upload to complete
                
                uploaded_files.append({
                    'fileName': file_path.name,
                    'fileType': file_type,
                    'result': result
                })
                
                self.logger.info(f"✅ Successfully uploaded: {file_path.name} as {file_type}")
                
        except Exception as e:
            self.logger.error(f"❌ Error uploading files: {e}")

        return uploaded_files
    
    def find_test_files(
        self,
        test_directory: str = '.'
    ) -> List[str]:
        """
        Find test files in the specified directory.
        
        Args:
            test_directory: Directory to search for test files
            
        Returns:
            List[str]: List of test file paths found
        """
        try:
            self.logger.info(f"Searching for test files in: {test_directory}")
            
            # Search patterns for performance test files and locustfile
            search_patterns = [
                os.path.join(test_directory, "perf_*.json"),
                os.path.join(test_directory, "perf_*_test.py"),
                os.path.join(test_directory, "**", "perf_*_test.py"),
                os.path.join(test_directory, "perf_*test.py"),
                os.path.join(test_directory, "**", "perf_*test.py"),
                os.path.join(test_directory, "locustfile.py"),
                os.path.join(test_directory, "requirements.txt")
            ]
            
            test_files = []
            for pattern in search_patterns:
                found_files = glob.glob(pattern, recursive=True)
                test_files.extend(found_files)
            
            # If no locustfile.py found, look for OSDU library version
            has_locustfile = any('locustfile.py' in f for f in test_files)
            if not has_locustfile:
                test_files.extend(self._find_osdu_locustfile())
            
            # Remove duplicates
            test_files = list(set(test_files))
            
            if test_files:
                self.logger.info(f"Found {len(test_files)} test file(s):")
                for file_path in test_files:
                    self.logger.info(f"  • {file_path}")
            else:
                self.logger.warning("No test files found!")
            
            return test_files
            
        except Exception as e:
            self.logger.error(f"Error finding test files: {e}")
            return []
    
    def _find_osdu_locustfile(self) -> List[str]:
        """
        Find the OSDU library locustfile.py if not present in user directory.
        
        Returns:
            List[str]: Path to OSDU locustfile.py if found, empty list otherwise
        """
        self.logger.info("🔍 No locustfile.py found, looking for OSDU library version...")
        
        try:
            import pkg_resources
            # Try to find the OSDU locustfile.py from the package
            osdu_locustfile = pkg_resources.resource_filename('osdu_perf.operations', 'locustfile.py')
            if os.path.exists(osdu_locustfile):
                self.logger.info(f"✅ Found OSDU locustfile.py: {osdu_locustfile}")
                return [osdu_locustfile]
        except (ImportError, Exception) as e:
            self.logger.warning(f"⚠️ Could not find OSDU locustfile.py in package: {e}")
        
        # Fallback: look in current directory
        current_dir = os.path.dirname(__file__)
        fallback_locustfile = os.path.join(current_dir, 'locustfile.py')
        if os.path.exists(fallback_locustfile):
            self.logger.info(f"✅ Found fallback locustfile.py: {fallback_locustfile}")
            return [fallback_locustfile]
        
        self.logger.warning("⚠️ No locustfile.py found in OSDU library")
        return []
