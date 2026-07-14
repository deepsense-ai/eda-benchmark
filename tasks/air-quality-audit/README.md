# deepsense/air-quality-audit

The agent audits an air-quality monitoring network in Wroclaw: given station
metadata, pollutant readings, and weather measurements, it must return the set
of 3 `station_id` values whose readings are least trustworthy (see
[instruction.md](instruction.md)). Each faulty station hides a different
mechanism — a lagged response to local changes, compressed dynamics (muted
swings), and residuals that correlate too neatly with weather drivers — while
decoy stations (high missingness, noisy-but-consistent, low variance) break
single-metric heuristics.
