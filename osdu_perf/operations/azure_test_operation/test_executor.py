"""Test execution management for Azure Load Testing."""

import logging
import time
from typing import Dict, Any, Optional
from azure.developer.loadtesting import LoadTestRunClient


class AzureLoadTestExecutor:
    """Manages test execution operations for Azure Load Testing."""
    
    def __init__(
        self,
        loadtest_run_client: LoadTestRunClient,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the test executor.
        
        Args:
            loadtest_run_client: Azure Load Test Run client for test execution
            logger: Logger instance
        """
        self.loadtest_run_client = loadtest_run_client
        self.logger = logger or logging.getLogger(__name__)
    
    def run_test(
        self,
        test_name: str,
        display_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Start a test execution using Azure Load Testing Data Plane API.
        
        Args:
            test_name: Name of the test to run
            display_name: Display name for the test run (optional)
            
        Returns:
            Dict[str, Any]: The test execution data, or None if failed
        """
        try:
            if not self.loadtest_run_client:
                raise ValueError("Data plane client not initialized. Create load test resource first.")

            self.logger.info(f"Starting test run for test '{test_name}'...")
            timestamp = int(time.time())
            
            # Ensure display name meets Azure Load Testing requirements (2-50 characters)
            if display_name:
                # Use provided display name but ensure it meets length requirements
                if len(display_name) < 2:
                    display_name = f"{display_name}-run"
                elif len(display_name) > 50:
                    display_name = display_name[:47] + "..."
            else:
                # Generate a display name that fits within limits
                base_name = test_name[:20] if len(test_name) > 20 else test_name
                display_name = f"{base_name}-{timestamp}"
                # Ensure it's within the 50 character limit
                if len(display_name) > 50:
                    # Truncate the base name to fit
                    max_base_length = 50 - len(f"-{timestamp}")
                    base_name = test_name[:max_base_length] if len(test_name) > max_base_length else test_name
                    display_name = f"{base_name}-{timestamp}"

            # Prepare test run configuration
            test_run_config = {
                'testId': test_name,
                'displayName': display_name,
                'description': f"Load test run created by osdu_perf framework"
            }
            
            # Start the test run
            result = self.loadtest_run_client.begin_test_run(
                test_run_id=display_name,
                body=test_run_config
            )

            self.logger.info(f"✅ Test run '{test_name}' started successfully with display name '{display_name}'")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error running test '{test_name}': {e}")
            return None
    
    def get_test_run_status(
        self,
        test_run_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the status of a test run.
        
        Args:
            test_run_id: ID of the test run to check
            
        Returns:
            Dict[str, Any]: Test run status information, or None if failed
        """
        try:
            self.logger.info(f"Getting status for test run '{test_run_id}'...")
            
            result = self.loadtest_run_client.get_test_run(test_run_id=test_run_id)
            
            status = result.get('status', 'UNKNOWN')
            self.logger.info(f"Test run status: {status}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error getting test run status: {e}")
            return None
    
    def wait_for_test_completion(
        self,
        test_run_id: str,
        max_wait_time: int = 3600,
        check_interval: int = 30
    ) -> bool:
        """
        Wait for a test run to complete.
        
        Args:
            test_run_id: ID of the test run to wait for
            max_wait_time: Maximum time to wait in seconds (default: 1 hour)
            check_interval: How often to check status in seconds (default: 30s)
            
        Returns:
            bool: True if test completed successfully, False otherwise
        """
        try:
            self.logger.info(f"⏳ Waiting for test run '{test_run_id}' to complete...")
            start_time = time.time()
            
            while (time.time() - start_time) < max_wait_time:
                status_info = self.get_test_run_status(test_run_id)
                
                if not status_info:
                    self.logger.error("Failed to get test run status")
                    return False
                
                status = status_info.get('status', 'UNKNOWN')
                
                if status == 'DONE':
                    self.logger.info(f"✅ Test run completed successfully")
                    return True
                elif status in ['FAILED', 'CANCELLED']:
                    self.logger.error(f"❌ Test run ended with status: {status}")
                    return False
                elif status in ['EXECUTING', 'PROVISIONING', 'PROVISIONED', 'CONFIGURING']:
                    elapsed = int(time.time() - start_time)
                    self.logger.info(f"⏳ Test status: {status} (elapsed: {elapsed}s)")
                else:
                    self.logger.warning(f"⚠️ Unknown test status: {status}")
                
                time.sleep(check_interval)
            
            # Timeout reached
            elapsed_time = int(time.time() - start_time)
            self.logger.warning(f"⏱️ Test run timeout after {elapsed_time} seconds")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Error waiting for test completion: {e}")
            return False
    
    def stop_test_run(
        self,
        test_run_id: str
    ) -> bool:
        """
        Stop a running test.
        
        Args:
            test_run_id: ID of the test run to stop
            
        Returns:
            bool: True if test was stopped successfully, False otherwise
        """
        try:
            self.logger.info(f"Stopping test run '{test_run_id}'...")
            
            self.loadtest_run_client.begin_stop_test_run(test_run_id=test_run_id)
            
            self.logger.info(f"✅ Test run '{test_run_id}' stop requested")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping test run: {e}")
            return False
    
    def get_test_run_results(
        self,
        test_run_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the results of a completed test run.
        
        Args:
            test_run_id: ID of the test run
            
        Returns:
            Dict[str, Any]: Test run results, or None if failed
        """
        try:
            self.logger.info(f"Getting results for test run '{test_run_id}'...")
            
            result = self.loadtest_run_client.get_test_run(test_run_id=test_run_id)
            
            # Extract key metrics
            if result:
                status = result.get('status')
                start_time = result.get('startDateTime')
                end_time = result.get('endDateTime')
                
                self.logger.info(f"Test Run Results:")
                self.logger.info(f"  Status: {status}")
                self.logger.info(f"  Start Time: {start_time}")
                self.logger.info(f"  End Time: {end_time}")
                
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error getting test run results: {e}")
            return None
