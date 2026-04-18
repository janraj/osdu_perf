"""Run distributed Locust load tests inside an AKS cluster.

Subsystem layout:

* :mod:`builder` — build the test image and push to Azure Container Registry.
* :mod:`manifests` — render ServiceAccount, Service, and master/worker
  Deployment manifests from string templates.
* :mod:`cluster` — thin ``kubectl`` and ``az`` subprocess wrappers.
* :mod:`runner` — orchestrate end-to-end: build → push → apply → wait → logs.
"""

from .runner import K8sRunInputs, K8sRunner

__all__ = ["K8sRunInputs", "K8sRunner"]
