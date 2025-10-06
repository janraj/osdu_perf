# osdu_perf/locust/user_base.py
from locust import HttpUser, task, events, between
from ..core import ServiceOrchestrator, InputHandler
import logging

class PerformanceUser(HttpUser):
    """
    Base user class for performance testing with automatic service discovery.
    Inherit from this class in your locustfile.
    """

    # Recommended default pacing between tasks (more realistic than no-wait)
    wait_time = between(1, 3)
    host = "https://localhost"  # Default host for testing

    def __init__(self, environment):
        super().__init__(environment)
        self.service_orchestrator = ServiceOrchestrator()
        self.input_handler = None
        self.services = []
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def on_start(self):
        """Initialize services and input handling"""
        self.logger.info(f"PerformanceUser on_start called subscription id is {self.environment}")
        self.input_handler = InputHandler(self.environment)
        self.service_orchestrator.register_service(self.client)
        self.services = self.service_orchestrator.get_services()
    
    @task
    def execute_services(self):
        """Execute all registered services"""
        for service in self.services:
            # make a per-service copy of the base headers so Authorization doesn't leak between services
            header = dict(self.input_handler.header)
            if hasattr(service, 'provide_explicit_token') and callable(service.provide_explicit_token):
                print("[PerformanceUser][provide_explicit_token] Checking any explicit token provided or not")
                try:
                    token = service.provide_explicit_token()
                    # if subclass implemented the method but returned nothing (e.g. `pass` -> None), skip setting Authorization
                    if token:
                        header['Authorization'] = f"Bearer {token}"
                except Exception as e:
                    self.logger.error(f"Providing explicit token failed: {e}")
   
            if hasattr(service, 'prehook') and callable(service.prehook):
                try:
                    service.prehook(
                        headers=header, 
                        partition=self.input_handler.partition,
                        base_url=self.input_handler.base_url
                    )
                except Exception as e:
                    self.logger.error(f"Service prehook failed: {e}")
                    continue  # Skip this service if prehook fails
   

            if hasattr(service, 'execute') and callable(service.execute):
                try:
                    service.execute(
                        headers=header,
                        partition=self.input_handler.partition,
                        base_url=self.input_handler.base_url
                    )
                except Exception as e:
                    self.logger.error(f"Service execution failed: {e}")

            if hasattr(service, 'posthook') and callable(service.posthook):
                try:
                    service.posthook(
                        headers=header,
                        partition=self.input_handler.partition,
                        base_url=self.input_handler.base_url
                    )
                except Exception as e:
                    self.logger.error(f"Service posthook failed: {e}")