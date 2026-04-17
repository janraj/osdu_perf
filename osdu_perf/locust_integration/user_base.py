# osdu_perf/locust/user_base.py
from locust import HttpUser, task, events, between
from ..operations.service_orchestrator import ServiceOrchestrator
from ..operations.input_handler import   InputHandler
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
import json

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
    _start_banner_printed = False
    
    @staticmethod
    def _setup_logging():
        """Return the module logger.

        Locust configures the root logger with its own handler/formatter. We
        just reuse that pipeline instead of attaching our own handler, which
        previously caused every line to be printed twice (once by our handler,
        once by locust's root handler via propagation).
        """
        logger = logging.getLogger(__name__)
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

        # Print the test-start banner once per process (first user wins). The
        # test_start listener also tries to print it, but at that point the
        # InputHandler hasn't been created yet, so we repeat here with full
        # details available.
        if not PerformanceUser._start_banner_printed:
            PerformanceUser._print_start_banner(environment, self.logger)
            PerformanceUser._start_banner_printed = True
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

    def get_request_headers(self, extra=None):
        """Return a fresh copy of headers with a unique correlation-id.

        Use this per-request (instead of caching ``get_headers()``) so each
        outbound request gets a distinct correlation-id of the form
        ``<test_run_id>-<hostname>-<counter>``.
        """
        return self.input_handler.build_request_headers(extra=extra)

    def new_correlation_id(self):
        """Return a unique correlation-id string for a single request."""
        return self.input_handler.new_correlation_id()
    
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
        merged_headers = self.input_handler.build_request_headers()
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

    @events.test_start.add_listener
    def on_test_start(environment, **kwargs):
        """Called once when the test starts.

        The actual banner is printed from the first user's ``__init__`` so the
        ``InputHandler`` (metadata/scenario) is fully populated. We keep
        this listener as a hook for future bookkeeping.
        """
        return

    @staticmethod
    def _print_start_banner(environment, logger):
        """Render the test-start info banner. Safe to call at test_start or on first user init."""
        input_handler = PerformanceUser._input_handler_instance

        test_run_id = (
            os.getenv("TEST_RUN_ID_NAME")
            or os.getenv("TEST_RUN_ID")
            or (getattr(input_handler, "_test_run_id", None) if input_handler else None)
            or "unknown"
        )
        host = getattr(environment, "host", None) or os.getenv("LOCUST_HOST", "unknown")
        parsed_options = getattr(environment, "parsed_options", None)
        partition = (
            (getattr(input_handler, "partition", None) if input_handler else None)
            or getattr(parsed_options, "partition", None)
            or os.getenv("PARTITION", "unknown")
        )
        app_id = (
            (getattr(input_handler, "app_id", None) if input_handler else None)
            or getattr(parsed_options, "appid", None)
            or os.getenv("APPID", "unknown")
        )
        scenario = os.getenv("TEST_SCENARIO") or (
            input_handler.get_test_scenario(os.getenv("LOCUST_TAGS"))
            if input_handler else ""
        ) or "-"

        # Resolve test metadata from InputHandler (populated from
        # system_config.yaml test_metadata + per-scenario overrides).
        metadata = {}
        if input_handler:
            try:
                metadata = input_handler.get_test_metadata() or {}
            except Exception:
                metadata = {}

        users = getattr(parsed_options, "num_users", None) if parsed_options else None
        spawn_rate = getattr(parsed_options, "spawn_rate", None) if parsed_options else None
        run_time = getattr(parsed_options, "run_time", None) if parsed_options else None
        tags = getattr(parsed_options, "tags", None) if parsed_options else None
        env_label = "Azure Load Test" if os.getenv("AZURE_LOAD_TEST", "").lower() == "true" else "Local"

        rows = [
            ("Test Run ID", test_run_id),
            ("Environment", env_label),
            ("Host",        host),
            ("Partition",   partition),
            ("App ID",      app_id),
            ("Scenario",    scenario),
            ("Tags",        ",".join(tags) if isinstance(tags, list) else (tags or "-")),
            ("Users",       users if users is not None else "-"),
            ("Spawn rate",  spawn_rate if spawn_rate is not None else "-"),
            ("Run time",    run_time or "-"),
        ]
        if metadata:
            # Print each metadata key on its own indented row for readability.
            rows.append(("Metadata", ""))
            for mk, mv in metadata.items():
                rows.append((f"  {mk}", mv))

        key_width = max(len(k) for k, _ in rows)
        val_width = max(len(str(v)) for _, v in rows)
        inner_width = key_width + 3 + val_width
        border = "=" * (inner_width + 4)

        logger.info(border)
        logger.info("  OSDU Performance Test - Starting")
        logger.info(border)
        for key, value in rows:
            logger.info(f"  {key.ljust(key_width)} : {value}")
        logger.info(border)

    @events.test_stop.add_listener
    def on_test_stop(environment, **kwargs):
        """Called once when the test finishes."""
        logger = logging.getLogger(__name__)

        # Get Kusto configuration from InputHandler
        kusto_config = PerformanceUser._kusto_config
        input_handler = PerformanceUser._input_handler_instance
        
        if not kusto_config or not input_handler:
            logger.warning("No Kusto configuration available, skipping metrics push")
            return
        
        if not input_handler.is_kusto_enabled():
            logger.info("Kusto metrics collection is disabled")
            return
        
        test_run_environment = "Local"
        try:
            # Automatically determine authentication method based on environment
            is_azure_load_test = os.getenv("AZURE_LOAD_TEST", "").lower() == "true"

            # QueuedIngestClient connects to the *ingest* endpoint
            # (https://ingest-<cluster>.<region>.kusto.windows.net), not the
            # query endpoint. Prefer the resolved ingest_uri; fall back to
            # cluster only if ingest_uri is missing for backward compat.
            ingest_endpoint = kusto_config.get('ingest_uri') or kusto_config.get('cluster_uri')

            if is_azure_load_test:
                test_run_environment = "Azure Load Test"
                auth_method = "managed_identity"
                logger.info(f"Pushing metrics to Kusto: {ingest_endpoint}/{kusto_config['database']}")
                logger.info(f"Using authentication method: {auth_method} (Azure Load Test environment detected)")
                kcsb = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(ingest_endpoint)
            else:
                auth_method = "az_cli"
                logger.info(f"Pushing metrics to Kusto: {ingest_endpoint}/{kusto_config['database']}")
                logger.info(f"Using authentication method: {auth_method} (local environment detected)")
                kcsb = KustoConnectionStringBuilder.with_az_cli_authentication(ingest_endpoint)
            
            ingest_client = QueuedIngestClient(kcsb)
            
            # Use existing test run ID from environment or generate fallback
            test_run_id = os.getenv("TEST_RUN_ID_NAME", None) or os.getenv("TEST_RUN_ID", None)
            if not test_run_id:
                # Fallback to UUID if TEST_RUN_ID not available (shouldn't happen in normal flow)
                test_run_id = str(uuid.uuid4())
                logger.warning(f"TEST_RUN_ID not found in environment, using fallback: {test_run_id}")
            
            logger.info(f"Using Test Run ID : {test_run_id}")
                
            current_timestamp = datetime.utcnow()

            test_scenario = input_handler.get_test_scenario(os.getenv("LOCUST_TAGS", None) )
            
            adme = PerformanceUser.get_ADME_name(environment.host)
            partition = input_handler.partition if input_handler else os.getenv("PARTITION", "Unknown")

            # Resolve per-run free-form metadata from InputHandler.
            test_metadata: dict = {}
            try:
                test_metadata = input_handler.get_test_metadata() if input_handler else {}
            except Exception as meta_err:
                logger.debug(f"Failed to read metadata from InputHandler: {meta_err}")
                test_metadata = {}

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
                logger.error(f"Error calculating test metrics: {e}")
                test_duration = 0
                max_rps = 0

            # 1. PREPARE STATS DATA
            stats_results = []
            for entry in stats.entries.values():
                service = PerformanceUser.get_service_name(entry.name)
                start_time = datetime.fromtimestamp(entry.start_time).isoformat() if hasattr(entry, 'start_time') and entry.start_time is not None else current_timestamp.isoformat()
                end_time = datetime.fromtimestamp(entry.last_request_timestamp).isoformat() if hasattr(entry, 'last_request_timestamp') and entry.last_request_timestamp is not None else current_timestamp.isoformat()
                start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                duration = (end - start).total_seconds()
                throughput = (entry.total_content_length / duration) if duration > 0 else 0
                average_rps = (entry.num_requests / duration) if duration > 0 else 0

                stats_results.append({
                    "ADME": adme,
                    "Partition": partition,
                    "Service": service,
                    "TestEnv": test_run_environment,
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
                    "AverageRPS": average_rps,
                    "RequestsPerSec": float(getattr(entry, 'num_reqs_per_sec', {}).get('total', 0) if hasattr(getattr(entry, 'num_reqs_per_sec', {}), 'get') else getattr(entry, 'num_reqs_per_sec', 0)),
                    "FailuresPerSec": float(getattr(entry, 'num_fail_per_sec', {}).get('total', 0) if hasattr(getattr(entry, 'num_fail_per_sec', {}), 'get') else getattr(entry, 'num_fail_per_sec', 0)),
                    "FailRatio": float(entry.fail_ratio) if hasattr(entry, 'fail_ratio') and entry.fail_ratio is not None else 0.0,
                    "TotalContentLength": int(entry.total_content_length) if hasattr(entry, 'total_content_length') and entry.total_content_length is not None else 0,
                    "StartTime": start_time,
                    "LastRequestTimestamp": end_time,
                    "Timestamp": current_timestamp.isoformat(),
                    "TestRunId": test_run_id,
                    "Throughput": throughput,
                    "TestScenario": test_scenario,
                    "Metadata": test_metadata,
                })
            
            # 2. PREPARE EXCEPTIONS DATA
            exceptions_results = []
            for error_key, error_entry in environment.runner.stats.errors.items():
                method = str(error_entry.method)
                name = str(error_entry.name)
                exceptions_results.append({
                    "TestRunId": test_run_id,
                    "ADME": adme,
                    "Partition": partition,
                    "Method": method,
                    "Name": name,
                    "TestEnv": test_run_environment,
                    "Error": str(error_entry.error) if hasattr(error_entry, 'error') else "Unknown",
                    "Occurrences": int(error_entry.occurrences) if hasattr(error_entry, 'occurrences') else 0,
                    "Traceback": str(getattr(error_entry, 'traceback', '')),
                    "ErrorMessage": str(getattr(error_entry, 'msg', '')),
                    "Service": PerformanceUser.get_service_name(name),
                    "Timestamp": current_timestamp.isoformat(),
                    "TestScenario": test_scenario,
                    "Metadata": test_metadata,
                })
            
            # 3. PREPARE SUMMARY DATA
            throughput = (stats.total.total_content_length / test_duration) if test_duration > 0 else 0
            average_rps = (stats.total.num_requests / test_duration) if test_duration > 0 else 0
            summary_results = [{
                "TestRunId": test_run_id,
                "ADME": adme,
                "Partition": partition,
                "TestEnv": test_run_environment,
                "TestScenario": test_scenario,
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
                "AverageRPS": float(average_rps),
                "Timestamp": current_timestamp.isoformat(),
                "Throughput": throughput,
                "Metadata": test_metadata,
            }]
            
            # INGEST DATA as newline-delimited JSON (MULTIJSON) so the
            # ``Metadata`` column can be ingested as a native dynamic value
            # instead of being stringified through CSV.
            def _ingest_json(rows: list, table: str, label: str):
                if not rows:
                    return
                props = IngestionProperties(
                    database=kusto_config['database'],
                    table=table,
                    data_format=DataFormat.MULTIJSON,
                )
                payload = "\n".join(json.dumps(r, default=str) for r in rows)
                ingest_client.ingest_from_stream(io.StringIO(payload), props)
                logger.info(f"{label} pushed to Kusto ({table}): {len(rows)} record(s)")

            _ingest_json(stats_results, "LocustMetricsV2", "Stats data")
            _ingest_json(exceptions_results, "LocustExceptionsV2", "Exceptions data")
            _ingest_json(summary_results, "LocustTestSummaryV2", "Summary data")

            logger.info(f"Test Run ID: {test_run_id}")

        except Exception as e:
            logger.error(f"Error pushing metrics to Kusto: {e}")
            # Optionally log the error details for debugging
            import traceback
            logger.error(f"Error details: {traceback.format_exc()}")

    @events.request.add_listener
    def on_request(request_type, name, response_time, response_length, response, **kwargs):
        # response_length is bytes returned from server
        pass 

   