# syntax=docker/dockerfile:1.6
# Image baked by `osdu_perf run k8s`. Bundles the user's test project + the
# osdu_perf wheel and exposes a single entrypoint that branches on $LOCUST_ROLE.
FROM mcr.microsoft.com/azurelinux/base/python:3.12

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LOCUST_ROLE=master

WORKDIR /app

# Project files (locustfile.py, perf_*_test.py, requirements.txt, *.whl, etc.)
# are copied as a single layer; .dockerignore in the project root may trim this.
COPY . /app/

# Install PyPI deps then the locally-built osdu_perf wheel (if present).
# Note: Azure Linux ships pip as an rpm package, so we don't try to upgrade it.
RUN tdnf install -y ca-certificates shadow-utils && \
    if [ -f /app/requirements.txt ]; then pip install -r /app/requirements.txt; fi && \
    WHEEL=$(ls /app/osdu_perf-*.whl 2>/dev/null | head -n1) && \
    if [ -n "$WHEEL" ]; then pip install --no-deps "$WHEEL"; fi && \
    tdnf clean all

# Drop privileges; ALT-style writable temp scratch area.
RUN useradd --uid 10001 --user-group --create-home --shell /sbin/nologin runner && \
    mkdir -p /tmp/locust && chown -R runner:runner /tmp/locust /app
USER runner

# Locust master listens for workers on 5557 and serves the (disabled) UI on 8089.
EXPOSE 5557 8089

ENTRYPOINT ["/app/_entrypoint.sh"]
