"""Trustworthy Anomaly Agent over ESA-ADB — modules [2][3][4] (the differentiator).

Base: ``config`` (path anchors + hyperparameters). Each numbered package is one PRD
feature. Downstream modules consume only the detector's cached outputs (continuous
score per window + windowed data), so the detector stays swappable.

  m1_detection   [1]  ESA's subsequence_if detector, vendored + thin glue
  m2_uncertainty [2]  raw score -> calibrated confidence + band U
  m3_attribution [3]  per-channel contribution for each detection
  m4_report      [4]  grounded generator + anti-hallucination judge
"""
