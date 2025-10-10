# osdu_perf/locust/user_base.py
from locust import HttpUser, task, events, between
from ..core import ServiceOrchestrator, InputHandler
import logging
from azure.kusto.ingest import QueuedIngestClient, IngestionProperties
from azure.kusto.data import KustoConnectionStringBuilder
from azure.kusto.ingest import QueuedIngestClient, IngestionProperties
from azure.kusto.data import DataFormat
from urllib.parse import urlparse
import os
import uuid
from datetime import datetime
import io
import csv

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
            try:
                total_bytes = sum(s.total_response_length for s in environment.runner.stats.entries.values())
                total_time = environment.runner.stats.total.last_request_timestamp - environment.runner.stats.total.start_time
                throughput_bps = total_bytes / total_time
                throughput_mbps = throughput_bps / (1024 * 1024)
            except Exception as e:
                print(f"Error calculating throughput metrics: {e}")
                throughput_bps = 0
                throughput_mbps = 0

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
                    "MinResponseTime": entry.min_response_time,
                    "MaxResponseTime": entry.max_response_time,
                    "ResponseTime50th": entry.get_response_time_percentile(0.5),
                    "ResponseTime60th": entry.get_response_time_percentile(0.6),
                    "ResponseTime70th": entry.get_response_time_percentile(0.7),
                    "ResponseTime80th": entry.get_response_time_percentile(0.8),
                    "ResponseTime90th": entry.get_response_time_percentile(0.9),
                    "ResponseTime95th": entry.get_response_time_percentile(0.95),
                    "ResponseTime98th": entry.get_response_time_percentile(0.98),
                    "ResponseTime99th": entry.get_response_time_percentile(0.99),
                    "ResponseTime999th": entry.get_response_time_percentile(0.999),
                    "CurrentRPS": float(entry.current_rps) if hasattr(entry, 'current_rps') and entry.current_rps is not None else 0.0,
                    "CurrentFailPerSec": float(entry.current_fail_per_sec) if hasattr(entry, 'current_fail_per_sec') and entry.current_fail_per_sec is not None else 0.0,
                    "MaxRPS": max_rps,
                    "RequestsPerSec": float(getattr(entry, 'num_reqs_per_sec', {}).get('total', 0) if hasattr(getattr(entry, 'num_reqs_per_sec', {}), 'get') else getattr(entry, 'num_reqs_per_sec', 0)),
                    "FailuresPerSec": float(getattr(entry, 'num_fail_per_sec', {}).get('total', 0) if hasattr(getattr(entry, 'num_fail_per_sec', {}), 'get') else getattr(entry, 'num_fail_per_sec', 0)),
                    "FailRatio": float(entry.fail_ratio) if hasattr(entry, 'fail_ratio') and entry.fail_ratio is not None else 0.0,
                    "TotalContentLength": int(entry.total_content_length) if hasattr(entry, 'total_content_length') and entry.total_content_length is not None else 0,
                    "StartTime": datetime.fromtimestamp(entry.start_time).isoformat() if hasattr(entry, 'start_time') and entry.start_time is not None else current_timestamp.isoformat(),
                    "LastRequestTimestamp": datetime.fromtimestamp(entry.last_request_timestamp).isoformat() if hasattr(entry, 'last_request_timestamp') and entry.last_request_timestamp is not None else current_timestamp.isoformat(),
                    "Timestamp": current_timestamp.isoformat(),
                    "TestRunId": test_run_id
                })
            
            # 2. PREPARE EXCEPTIONS DATA
            exceptions_results = []
            for error_key, error_entry in environment.runner.stats.errors.items():
                exceptions_results.append({
                    "TestRunId": test_run_id,
                    "ADME": adme,
                    "SKU": sku,
                    "Version": version,
                    "Partition": partition,
                    "Method": str(error_key[0]) if error_key[0] else "Unknown",
                    "Name": str(error_key[1]) if error_key[1] else "Unknown",
                    "Error": str(error_entry.error) if hasattr(error_entry, 'error') else "Unknown",
                    "Occurrences": int(error_entry.occurrences) if hasattr(error_entry, 'occurrences') else 0,
                    "Traceback": str(getattr(error_entry, 'traceback', '')),
                    "ErrorMessage": str(getattr(error_entry, 'msg', '')),
                    "Service": PerformanceUser.get_service_name(str(error_key[1]) if error_key[1] else ""),
                    "Timestamp": current_timestamp.isoformat()
                })
            
            # 3. PREPARE SUMMARY DATA
            summary_results = [{
                "TestRunId": test_run_id,
                "ADME": adme,
                "Partition": partition,
                "SKU": sku,
                "Version": version,
                "TotalRequests": int(stats.total.num_requests),
                "TotalFailures": int(stats.total.num_failures),
                "MedianResponseTime": float(stats.total.median_response_time),
                "AvgResponseTime": float(stats.total.avg_response_time),
                "MinResponseTime": float(stats.total.min_response_time),
                "MaxResponseTime": float(stats.total.max_response_time),
                "ResponseTime50th": float(stats.total.get_response_time_percentile(0.5)),
                "ResponseTime60th": float(stats.total.get_response_time_percentile(0.6)),
                "ResponseTime70th": float(stats.total.get_response_time_percentile(0.7)),
                "ResponseTime80th": float(stats.total.get_response_time_percentile(0.8)),
                "ResponseTime90th": float(stats.total.get_response_time_percentile(0.9)),
                "ResponseTime95th": float(stats.total.get_response_time_percentile(0.95)),
                "ResponseTime98th": float(stats.total.get_response_time_percentile(0.98)),
                "ResponseTime99th": float(stats.total.get_response_time_percentile(0.99)),
                "ResponseTime999th": float(stats.total.get_response_time_percentile(0.999)),
                "CurrentRPS": float(stats.total.current_rps) if hasattr(stats.total, 'current_rps') and stats.total.current_rps is not None else 0.0,
                "CurrentFailPerSec": float(stats.total.current_fail_per_sec) if hasattr(stats.total, 'current_fail_per_sec') and stats.total.current_fail_per_sec is not None else 0.0,
                "RequestsPerSec": float(getattr(stats.total, 'num_reqs_per_sec', {}).get('total', 0) if hasattr(getattr(stats.total, 'num_reqs_per_sec', {}), 'get') else getattr(stats.total, 'num_reqs_per_sec', 0)),
                "FailuresPerSec": float(getattr(stats.total, 'num_fail_per_sec', {}).get('total', 0) if hasattr(getattr(stats.total, 'num_fail_per_sec', {}), 'get') else getattr(stats.total, 'num_fail_per_sec', 0)),
                "FailRatio": float(stats.total.fail_ratio) if hasattr(stats.total, 'fail_ratio') and stats.total.fail_ratio is not None else 0.0,
                "TotalContentLength": int(stats.total.total_content_length) if hasattr(stats.total, 'total_content_length') and stats.total.total_content_length is not None else 0,
                "StartTime": start_time.isoformat() if start_time and hasattr(start_time, 'isoformat') else current_timestamp.isoformat(),
                "EndTime": current_timestamp.isoformat(),
                "TestDurationSeconds": float(test_duration),
                "MaxRPS": float(max_rps),
                "Timestamp": current_timestamp.isoformat()
            }]
            
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
            
            
            def create_csv_string(data_list, headers):
                """Create CSV string from list of dictionaries"""
                if not data_list:
                    return ""
                
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data_list)
                return output.getvalue()

            # INGEST DATA using CSV format
            if stats_results:
                stats_headers = ["ADME", "Partition", "SKU", "Version", "Service", "Name", "Method", 
                               "Requests", "Failures", "MedianResponseTime", "AverageResponseTime",
                               "MinResponseTime", "MaxResponseTime", "ResponseTime50th", "ResponseTime60th",
                               "ResponseTime70th", "ResponseTime80th", "ResponseTime90th", "ResponseTime95th",
                               "ResponseTime98th", "ResponseTime99th", "ResponseTime999th", "CurrentRPS",
                               "CurrentFailPerSec", "MaxRPS", "RequestsPerSec", "FailuresPerSec", 
                               "FailRatio", "TotalContentLength", "StartTime", "LastRequestTimestamp",
                               "Timestamp", "TestRunId"]
                stats_csv = create_csv_string(stats_results, stats_headers)
                ingest_client.ingest_from_stream(
                    io.StringIO(stats_csv), 
                    stats_ingestion_props
                )
                print(f"✅ Stats data pushed to Kusto (LocustMetrics table): {len(stats_results)} records")

            if exceptions_results:
                exceptions_headers = ["TestRunId", "ADME", "SKU", "Version", "Partition", "Method", "Name", "Error", 
                                    "Occurrences", "Traceback", "ErrorMessage", "Service", "Timestamp"]
                exceptions_csv = create_csv_string(exceptions_results, exceptions_headers)
                ingest_client.ingest_from_stream(
                    io.StringIO(exceptions_csv), 
                    exceptions_ingestion_props
                )
                print(f"✅ Exceptions data pushed to Kusto (LocustExceptions table): {len(exceptions_results)} records")

            if summary_results:
                summary_headers = ["TestRunId", "ADME", "Partition", "SKU", "Version", "TotalRequests", 
                                 "TotalFailures", "MedianResponseTime", "AvgResponseTime", "MinResponseTime", 
                                 "MaxResponseTime", "ResponseTime50th", "ResponseTime60th", "ResponseTime70th", 
                                 "ResponseTime80th", "ResponseTime90th", "ResponseTime95th", "ResponseTime98th", 
                                 "ResponseTime99th", "ResponseTime999th", "CurrentRPS", "CurrentFailPerSec", 
                                 "RequestsPerSec", "FailuresPerSec", "FailRatio", "TotalContentLength", 
                                 "StartTime", "EndTime", "TestDurationSeconds", "MaxRPS", "Timestamp"]
                summary_csv = create_csv_string(summary_results, summary_headers)
                ingest_client.ingest_from_stream(
                    io.StringIO(summary_csv), 
                    summary_ingestion_props
                )
                print(f"✅ Summary data pushed to Kusto (LocustTestSummary table): 1 record")

            print(f"🆔 Test Run ID: {test_run_id}")

        except Exception as e:
            print(f"❌ Error pushing metrics to Kusto: {e}")
            # Optionally log the error details for debugging
            import traceback
            print(f"📋 Error details: {traceback.format_exc()}")

    @events.request.add_listener
    def on_request(request_type, name, response_time, response_length, response, **kwargs):
        # response_length is bytes returned from server
        pass 

   