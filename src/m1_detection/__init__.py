"""[1] Detection — thin adapter exposing the reproduced detector behind D7.

The real detector is ESA's own ``subsequence_if`` run verbatim in ``repro/``. This
package does NOT reimplement it; it only wraps ``repro`` output into a
``DetectionResult`` so the trustworthy layer stays detector-agnostic.
"""
