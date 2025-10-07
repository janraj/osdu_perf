# osdu_perf/locust/user_base.py
from locust import HttpUser, task, events, between
from ..core import ServiceOrchestrator, InputHandler
import logging
from azure.kusto.ingest import QueuedIngestClient, IngestionProperties
from azure.kusto.data import KustoConnectionStringBuilder
import pandas as pd
from azure.kusto.ingest import QueuedIngestClient, IngestionProperties
from azure.kusto.data import DataFormat
from urllib.parse import urlparse
import os

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
        """Called once when the test finishes."""
        # ✅ Initialize Kusto client (e.g., your own ADX cluster)
        KUSTO_CLUSTER = "https://testperfo.eastus.kusto.windows.net"
        KUSTO_DB = "testperfo"
        KUSTO_INGEST_URI = "https://ingest-testperfo.eastus.kusto.windows.net"
        KUSTO_TABLE = "LocustMetrics"

        #kcsb = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(KUSTO_CLUSTER)
        kcsb = KustoConnectionStringBuilder.with_az_cli_authentication(KUSTO_CLUSTER)
        ingest_client = QueuedIngestClient(kcsb)

        adme = PerformanceUser.get_ADME_name(environment.host)
        partition = os.getenv("PARTITION", "uNot Yet") 
        sku = "Not Yet" #self.input_handler.sku
        version = "Not yet" #self.input_handler.version
        

        stats = environment.runner.stats
        error_logs = environment.runner.errors
        exceptions = environment.runner.exceptions

        total_stats = stats.total
        
        # Calculate overall max RPS from total stats
        try:
            test_duration = (pd.Timestamp.utcnow() - pd.Timestamp(environment.runner.start_time)).total_seconds()
            max_rps = total_stats.num_requests / test_duration if test_duration > 0 else 0
        except Exception as e:
            print(f"Error calculating max RPS: {e}")
            max_rps = 0

        results = []
        for entry in stats.entries.values():
            service = PerformanceUser.get_service_name(entry.name)

            error_details = []
            exception_details = []

            # Process errors
            for error_key, error_entry in error_logs.items():
                if error_key[1] == entry.name:  # error_key is (method, name)
                    error_details.append({
                        "error": str(error_entry.error),
                        "occurrences": error_entry.occurrences
                    })
            
            # Process exceptions  
            for exc_key, exc_entry in exceptions.items():
                if exc_key[1] == entry.name:  # exc_key is (method, name)
                    exception_details.append({
                        "exception": str(exc_entry.get('exception', '')),
                        "count": exc_entry.get('count', 0),
                        "msg": str(exc_entry.get('msg', ''))
                    })


            results.append({
                "ADME": adme,
                "Partition": partition,
                "SKU": sku,
                "Version": version,
                "Service": service,
                "Name": entry.name,
                "Method": entry.method,
                "Requests": entry.num_requests,
                "Failures": entry.num_failures,
                "MedianResponseTime": entry.median_response_time,
                "AverageResponseTime": entry.avg_response_time,
                "Timestamp": pd.Timestamp.utcnow(),
                "CurrentRPS": entry.current_rps,  
                "Throughput": max_rps,                            # Type: float - CORRECTED
                "RequestsPerSec": entry.num_reqs_per_sec,         # Type: float
                "FailuresPerSec": entry.num_fail_per_sec,         # Type: float
                "FailRatio": entry.fail_ratio,                    # Type: float (0.0 to 1.0)
                "ErrorLogs": str(error_details),                  # Type: string (JSON)
                "Exceptions": str(exception_details)               # Type: string (JSON)
            })
        
        df = pd.DataFrame(results)
        ingestion_props = IngestionProperties(
            database=KUSTO_DB,
            table=KUSTO_TABLE,
            data_format=DataFormat.CSV
        )
        ingest_client.ingest_from_dataframe(df, ingestion_props)
        print("✅ Metrics pushed to Kusto")


   