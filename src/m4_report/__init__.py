"""[4] LLM layer — grounded generator + anti-hallucination judge.

Two-stage, the core differentiator of the project:
  generator  writes an operator report ONLY from window + channels + U; says "no sé"
             when signal is missing; labels hypotheses, never asserts un-grounded cause (D4).
  judge      audits the report against the data and flags/blocks unsupported claims (D5).

Consumes only D7 (``Detection``) + [2]/[3] outputs — never the raw full dataset.
"""
