"""[2] Uncertainty — turn a raw anomaly score into calibrated confidence + band U.

Conformal prediction (MAPIE) over a held-out calibration set, or MC-dropout/quantile
as fallback. Output attaches ``confidence`` and ``band`` to each detection so the
operator can prioritise honestly ("sure NO" vs "no idea").
"""
