# deepsense/parsing-values-task

The agent gets a messy transactions file (`data.csv`) and a long, precise
specification: parse dirty currency strings (credit tokens, parentheses
negatives, ambiguous thousand/decimal separators), extract structured fields
from free-text notes, compute a net amount, deduplicate records, filter to
Q4 2025, compute robust z-scores per (region, month) using median/MAD, and
return the top 10 `record_id` values ranked by anomaly score in exact order
(see [instruction.md](instruction.md)). The challenge is faithful rule
following — every parsing edge case and tie-breaking rule matters.
