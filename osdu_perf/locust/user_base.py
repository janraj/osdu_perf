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

    def __init__(self, environment):
        super().__init__(environment)
        self.service_orchestrator = ServiceOrchestrator()
        self.input_handler = None
        self.services = []
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def on_start(self):
        """Initialize services and input handling"""
        self.input_handler = InputHandler(self.environment)
        self.service_orchestrator.register_service(self.client)
        self.services = self.service_orchestrator.get_services()
    
    @task
    def execute_services(self):
        """Execute all registered services"""
        for service in self.services:
            if hasattr(service, 'execute') and callable(service.execute):
                try:
                    service.execute(
                        headers=self.input_handler.header,
                        partition=self.input_handler.partition,
                        base_url=self.input_handler.base_url
                    )
                except Exception as e:
                    self.logger.error(f"Service execution failed: {e}")
