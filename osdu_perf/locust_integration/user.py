# osdu_perf/locust_integration/user.py
from locust import HttpUser, task, events, between
from ..operations.service_orchestrator import ServiceOrchestrator
from ..operations.input_handler import   InputHandler
import logging
from urllib.parse import urlparse
import os
import uuid
from datetime import datetime

class PerformanceUser():
    """
    Base user class for performance testing with automatic service discovery.
    Inherit from this class in your locustfile.
    """
    abstract = True
    # Default pacing between tasks - will be updated from config in on_start
    wait_time = between(1, 3)
    host = "https://localhost"  # Default host for testing
    
    # Class-level storage for configuration (accessible in static methods)
    _kusto_config = None
    _input_handler_instance = None
    
    @staticmethod
    def _setup_logging():
        """Setup logging configuration with the specified format."""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s -  %(filename)s:%(funcName)s:%(lineno)d - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    

    def __init__(self, environment):
        self.environment = environment
        self.input_handler = None
        self.logger = self._setup_logging()

        self.logger.info(f"PerformanceUser on_start called environment is {self.environment}")
        self.input_handler = InputHandler(self.environment)
        
        # Store config at class level for access in static methods
        PerformanceUser._kusto_config = self.input_handler.get_kusto_config()
        PerformanceUser._input_handler_instance = self.input_handler      
 
    def get_host(self):
        """Return the host URL for this user"""
        return self.input_handler.base_url
    
    def get_partition(self):
        """Return the partition for this user"""
        return self.input_handler.partition
    
    def get_appid(self):
        """Return the app ID for this user"""
        return self.input_handler.app_id
    
    def get_token(self):
        """Return the token for this user"""
        return os.getenv('ADME_BEARER_TOKEN')
    
    def get_headers(self):
        """Return the default headers for this user"""
        return self.input_handler.header
    
    def get_logger(self):
        return self.logger
    
    def get(self, endpoint, name=None, headers=None, **kwargs):
        return self._request("GET", f"{self.input_handler.base_url}{endpoint}", name, headers, **kwargs)

    def post(self, endpoint, data=None, name=None, headers=None, **kwargs):
        return self._request("POST", f"{self.input_handler.base_url}{endpoint}", name, headers, json=data, **kwargs)

    def put(self, endpoint, data=None, name=None, headers=None, **kwargs):
        return self._request("PUT", f"{self.input_handler.base_url}{endpoint}", name, headers, json=data, **kwargs)

    def delete(self, endpoint, name=None, headers=None, **kwargs):
        return self._request("DELETE", f"{self.input_handler.base_url}{endpoint}", name, headers, **kwargs)

    def _request(self, method, url, name, headers, **kwargs):
        self.logger.info(f"[PerformanceUser] Making {method} request to {url} with name={name} ")   
        merged_headers = dict(self.input_handler.header)
        token = os.getenv("ADME_BEARER_TOKEN", None)
        if token:
            self.logger.debug("[PerformanceUser] Using ADME_BEARER_TOKEN from environment for Authorization header")
            merged_headers['Authorization'] = f"Bearer {token}"
        if headers:
            self.logger.debug(f"[PerformanceUser] Merging additional headers: {headers}")   
            merged_headers.update(headers)

        with self.client.request(method=method,url=url,headers=merged_headers,name=name,catch_response=True,**kwargs) as response:
            if not response.ok:
                self.logger.error(f"[PerformanceUser] {method} {url} failed with status code {response.status_code}")   
                response.failure(f"{method} {url} failed with {response.status_code}")
            self.logger.debug(f"[PerformanceUser] {method} {url} succeeded with status code {response.status_code}")
  
    @staticmethod
    def get_ADME_name(host):
        """Return the ADME name for this user class"""
        try:
            parsed = urlparse(host)
            return parsed.hostname or parsed.netloc.split(':')[0]
        except Exception:
            return "unknown"
    @staticmethod
    def get_service_name(url_path):
        """Return the Service name for this user class"""
        try:
            parsed = urlparse(url_path)
            return parsed.path.split('/')[2] or "unknown"
        except Exception:
            return "unknown"

    @events.test_stop.add_listener
    def on_test_stop(environment, **kwargs):
        """Called once when the test finishes — dispatches metrics to enabled telemetry plugins."""
        logger = logging.getLogger(__name__)

        input_handler = PerformanceUser._input_handler_instance
        if not input_handler:
            logger.warning("No InputHandler available, skipping metrics push")
            return

        from ..telemetry import TelemetryDispatcher, discover_plugins
        config = input_handler.get_metrics_collector_config()
        dispatcher = TelemetryDispatcher(plugins=discover_plugins(), config=config)
        dispatcher.dispatch(environment, input_handler)

    @events.request.add_listener
    def on_request(request_type, name, response_time, response_length, response, **kwargs):
        # response_length is bytes returned from server
        pass 

   