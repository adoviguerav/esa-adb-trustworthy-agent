"""[1] Detection — ESA's ``subsequence_if`` detector, vendored and reproduced.

The detector is ESA's own code run verbatim (``vendor/algorithm.py``, via its JSON
CLI). This package does NOT reimplement it: ``model.py`` wires train/score and caches
outputs, ``evaluation.py`` computes the official event-wise metric (0.9487), and
``preprocessing.py`` turns the raw Zenodo dump into the canonical train/test CSVs.
"""
