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
import json
import tempfile
import uuid
from datetime import datetime

class PerformanceUser(HttpUser):
    """
    Base user class for performance testing with automatic service discovery.
    Inherit from this class in your locustfile.
    """

    # Default pacing between tasks - will be updated from config in on_start
    wait_time = between(1, 3)
    host = "https://localhost"  # Default host for testing
    
    # Class-level storage for configuration (accessible in static methods)
    _kusto_config = None
    _input_handler_instance = None

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
        
        # Store config at class level for access in static methods
        PerformanceUser._kusto_config = self.input_handler.get_kusto_config()
        PerformanceUser._input_handler_instance = self.input_handler
        
        
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
        # Get Kusto configuration from InputHandler
        kusto_config = PerformanceUser._kusto_config
        input_handler = PerformanceUser._input_handler_instance
        
        if not kusto_config or not input_handler:
            print("⚠️  No Kusto configuration available, skipping metrics push")
            return
        
        if not input_handler.is_kusto_enabled():
            print("ℹ️  Kusto metrics collection is disabled")
            return
        
        try:
            # Automatically determine authentication method based on environment
            is_azure_load_test = os.getenv("AZURE_LOAD_TEST", "").lower() == "true"
            
            if is_azure_load_test:
                auth_method = "managed_identity"
                print(f"📊 Pushing metrics to Kusto: {kusto_config['cluster']}/{kusto_config['database']}")
                print(f"🔐 Using authentication method: {auth_method} (Azure Load Test environment detected)")
                kcsb = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(kusto_config['cluster'])
            else:
                auth_method = "az_cli"
                print(f"📊 Pushing metrics to Kusto: {kusto_config['cluster']}/{kusto_config['database']}")
                print(f"🔐 Using authentication method: {auth_method} (local environment detected)")
                kcsb = KustoConnectionStringBuilder.with_az_cli_authentication(kusto_config['cluster'])
            
            ingest_client = QueuedIngestClient(kcsb)
            
            # Use existing test run ID from environment or generate fallback
            test_run_id = os.getenv("TEST_RUN_ID")
            if not test_run_id:
                # Fallback to UUID if TEST_RUN_ID not available (shouldn't happen in normal flow)
                test_run_id = str(uuid.uuid4())
                print(f"⚠️  TEST_RUN_ID not found in environment, using fallback: {test_run_id}")
            else:
                print(f"📋 Using Test Run ID from environment: {test_run_id}")
                
            current_timestamp = datetime.utcnow()
            
            adme = PerformanceUser.get_ADME_name(environment.host)
            partition = input_handler.partition if input_handler else os.getenv("PARTITION", "Unknown")
            sku = "Not Yet"
            version = "Not yet"
            
            # Calculate test duration and max RPS
            stats = environment.runner.stats
            try:
                start_time = getattr(environment.runner, 'start_time', None)
                if start_time:
                    test_duration = (current_timestamp - start_time).total_seconds()
                    max_rps = stats.total.num_requests / test_duration if test_duration > 0 else 0
                else:
                    test_duration = 0
                    max_rps = 0
            except Exception as e:
                print(f"Error calculating test metrics: {e}")
                test_duration = 0
                max_rps = 0
            
            # 1. PREPARE STATS DATA
            stats_results = []
            for entry in stats.entries.values():
                service = PerformanceUser.get_service_name(entry.name)
                stats_results.append({
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
                    "CurrentRPS": entry.current_rps,
                    "Throughput": max_rps,
                    "RequestsPerSec": entry.num_reqs_per_sec,
                    "FailuresPerSec": entry.num_fail_per_sec,
                    "FailRatio": entry.fail_ratio,
                    "Timestamp": current_timestamp,
                    "TestRunId": test_run_id
                })
            
            # 2. PREPARE EXCEPTIONS DATA
            exceptions_results = []
            for error_key, error_entry in environment.runner.stats.errors.items():
                exceptions_results.append({
                    "TestRunId": test_run_id,
                    "Method": str(error_key[0]) if error_key[0] else "Unknown",
                    "Name": str(error_key[1]) if error_key[1] else "Unknown",
                    "Error": str(error_entry.error) if hasattr(error_entry, 'error') else "Unknown",
                    "Occurrences": int(error_entry.occurrences) if hasattr(error_entry, 'occurrences') else 0,
                    "Traceback": str(getattr(error_entry, 'traceback', '')),
                    "Timestamp": current_timestamp
                })
            
            # 3. PREPARE SUMMARY DATA
            summary_results = [{
                "TestRunId": test_run_id,
                "ADME": adme,
                "Partition": partition,
                "TotalRequests": int(stats.total.num_requests),
                "TotalFailures": int(stats.total.num_failures),
                "AvgResponseTime": float(stats.total.avg_response_time),
                "StartTime": start_time if start_time else current_timestamp,
                "EndTime": current_timestamp,
                "TestDurationSeconds": float(test_duration),
                "MaxRPS": float(max_rps),
                "Timestamp": current_timestamp
            }]
            
            # CREATE DATAFRAMES
            stats_df = pd.DataFrame(stats_results)
            exceptions_df = pd.DataFrame(exceptions_results) if exceptions_results else pd.DataFrame()
            summary_df = pd.DataFrame(summary_results)
            
            # CREATE INGESTION PROPERTIES
            stats_ingestion_props = IngestionProperties(
                database=kusto_config['database'],
                table="LocustMetrics",
                data_format=DataFormat.CSV
            )
            
            exceptions_ingestion_props = IngestionProperties(
                database=kusto_config['database'],
                table="LocustExceptions",
                data_format=DataFormat.CSV
            )
            
            summary_ingestion_props = IngestionProperties(
                database=kusto_config['database'],
                table="LocustTestSummary",
                data_format=DataFormat.CSV
            )
            
            # INGEST DATA
            if not stats_df.empty:
                ingest_client.ingest_from_dataframe(stats_df, stats_ingestion_props)
                print(f"✅ Stats data pushed to Kusto (LocustStats table): {len(stats_results)} records")
            
            if not exceptions_df.empty:
                ingest_client.ingest_from_dataframe(exceptions_df, exceptions_ingestion_props)
                print(f"✅ Exceptions data pushed to Kusto (LocustExceptions table): {len(exceptions_results)} records")
            
            ingest_client.ingest_from_dataframe(summary_df, summary_ingestion_props)
            print(f"✅ Summary data pushed to Kusto (LocustTestSummary table): 1 record")
            print(f"🆔 Test Run ID: {test_run_id}")
            
        except Exception as e:
            print(f"❌ Error pushing metrics to Kusto: {e}")
            # Optionally log the error details for debugging
            import traceback
            print(f"📋 Error details: {traceback.format_exc()}")

   