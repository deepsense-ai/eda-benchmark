# deepsense/solar-farm-daily-yield

The agent computes the real energy production (kWh) for each of 24 solar
farms on UTC day 2024-03-15 from deliberately messy telemetry: 38 dataset
files including per-farm production CSVs in mixed encodings (UTF-8/UTF-16),
mixed separators and decimal conventions, mixed timestamp formats and local
time zones, a nested `sensors_calibration.json` (units, reading types,
calibration offsets, value column names), a free-text maintenance report
whose COMPLETED windows must be excluded, sentinel values, duplicates,
inverter-overheat safety windows, and decoy production files for farms that
are not in the fleet. The answer is a dict `farm_id -> integer kWh` (see
[instruction.md](instruction.md)).
