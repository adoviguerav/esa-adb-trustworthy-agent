"""Minimal vendored subset of ESA's TimeEval fork (kplabs-pl/ESA-ADB, MIT).

Only what preprocessing.py needs: the ``datasets`` subpackage (DatasetManager,
DatasetAnalyzer, DatasetRecord, per-channel metadata) and its ``utils.datasets``
helper. Package layout mirrors the original so relative imports work unchanged.
"""
