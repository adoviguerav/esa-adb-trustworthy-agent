"""Trustworthy Anomaly Agent over ESA-ADB — modules [2][3][4] (the differentiator).

Base: ``config`` (anchors) + ``interfaces`` (D7 contract). Each numbered package is
one PRD feature:

  m1_detection   [1]  adapter over ``repro/`` -> DetectionResult (D7)
  m2_uncertainty [2]  raw score -> calibrated confidence + band U
  m3_attribution [3]  per-channel contribution for each detection
  m4_report      [4]  grounded generator + anti-hallucination judge
"""
