"""Vendored ESA-ADB event-wise metric (ESAScores) — standalone, no esa-adb clone needed.

Source: github.com/kplabs-pl/ESA-ADB, ``timeeval/metrics/`` (MIT). Files are verbatim
copies of the minimal import closure of ``ESAScores``; see NOTICE at the repo root.
Importing from here (instead of ``timeeval.metrics``) avoids pulling TimeEval's
orchestration stack (dask, docker, ...).
"""
from .ESA_ADB_metrics import ESAScores

__all__ = ["ESAScores"]
