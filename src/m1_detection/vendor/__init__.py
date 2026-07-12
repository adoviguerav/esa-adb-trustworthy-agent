"""Vendored ESA-ADB code (MIT) — verbatim copies so the pipeline runs without the clone.

Contents (see NOTICE at the repo root for license and provenance):
  - ``algorithm.py``     — the ``subsequence_if`` detector (TimeEval-algorithms/subsequence_if/).
  - ``prep_utils.py``    — preprocessing helpers (notebooks/data-prep/utils.py).
  - ``timeeval_min/``    — ESA's multivariate fork of TimeEval's dataset management
                           (timeeval/datasets/ + timeeval/utils/datasets.py), needed by
                           preprocessing.py. NOT the PyPI ``timeeval``: ESA changed the
                           metadata to per-channel dicts (metadata.py:65-67).
"""
