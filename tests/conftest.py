# Shared fixtures for osdu_perf tests.
#
# Importing locust triggers gevent monkey-patching of stdlib (ssl, socket,
# subprocess, ...). If anything else imports `ssl` first (e.g. azure SDKs),
# gevent emits a MonkeyPatchWarning and on some Python versions we hit a
# RecursionError. Force the locust import here so it always wins.
import locust  # noqa: F401
