"""Reference solver for the reactor meltdown task."""
from pathlib import Path

import numpy as np
import pandas as pd

# Minimum OOR readings needed for a reliable regression fit.
# Discoverable from data: fewer than ~10 points make the linear fit
# unstable under the sensor noise present in this dataset.  Any value
# from 5 to 20 gives the same result here.
MIN_REGRESSION_POINTS: int = 10

# A gap of at least this many minutes between consecutive OOR readings
# marks the boundary between a phantom glitch and the real cascade.
# Discoverable from data: phantom glitches last ≤ 25 min and the gap
# to the next OOR episode is at least 114 min (COOLING_PRES_01, the
# shortest gap).  Any threshold in (25, 114) works; 60 is a
# conservative midpoint.
PHANTOM_GAP_MINUTES: int = 60

# Deviation magnitude above which a sensor reading is in the plateau
# region (expressed as a fraction of normal_range).  The physical
# model caps deviation at 0.80 × normal_range; readings beyond 0.75
# are already in the flat-top region.  Including plateau readings
# collapses the fitted slope toward zero, pushing the extrapolated
# onset into the future.  Discoverable from data: any sensor's OOR
# time series shows a clear levelling-off above this threshold.
SATURATION_FRACTION: float = 0.75


def solve(data_folder: str) -> list[str]:
    """Return the full causal propagation order of the five subsystems.

    Steps:
      1. Load sensor readings and metadata; join on sensor_id.
      2. Normalise each reading to UTC by subtracting the logger's
         UTC offset (logger_utc_offset_hours from metadata); compute
         integer minute offsets from the UTC simulation start.
      3. Compute physically-corrected minutes by further subtracting
         each sensor's response_delay_minutes.
      4. For each sensor, find out-of-range readings, discard
         phantom-glitch readings via gap analysis
         (PHANTOM_GAP_MINUTES), filter to pre-saturation readings
         (SATURATION_FRACTION), fit a linear regression through those
         readings, and back-extrapolate to the minute where the
         regression line crosses the sensor's normal-range centre.
         This gives the true physical onset regardless of how fast or
         slow each subsystem deteriorates.
      5. Per subsystem, take the earliest regression-based onset
         across its sensors.
      6. Sort subsystems by onset minute; return the full order,
         earliest first.

    Args:
        data_folder: Path to the directory containing the six CSV
            files.

    Returns:
        Five-element list of all subsystems ordered by physical onset,
        earliest first.
    """
    folder = Path(data_folder)

    # Step 1 — load and join
    sensors = pd.concat(
        [
            pd.read_csv(folder / "sensors_01.csv"),
            pd.read_csv(folder / "sensors_02.csv"),
            pd.read_csv(folder / "sensors_03.csv"),
        ],
        ignore_index=True,
    )
    metadata = pd.read_csv(folder / "sensor_metadata.csv")
    sensors = sensors.merge(metadata, on="sensor_id", how="left")

    sensors["timestamp"] = pd.to_datetime(sensors["timestamp"])

    # Step 2 — normalise to UTC: each logger stores timestamps in its
    # own local time zone; subtract the UTC offset to recover the true
    # UTC time before comparing readings across subsystems.
    sensors["utc_timestamp"] = sensors["timestamp"] - pd.to_timedelta(
        sensors["logger_utc_offset_hours"] * 60, unit="m"
    )
    simulation_start = sensors["utc_timestamp"].min()

    # Convert UTC timestamps to integer minutes from simulation start
    sensors["minute"] = (
        sensors["utc_timestamp"] - simulation_start
    ).dt.total_seconds().astype(int) // 60

    # Step 3 — subtract sensor response delay
    sensors["corrected_minute"] = (
        sensors["minute"] - sensors["response_delay_minutes"]
    )

    # Step 4 & 5 — regression per sensor, aggregate per subsystem
    subsystem_onsets: dict[str, float] = {}

    for sensor_id, group in sensors.groupby("sensor_id"):
        row = metadata[metadata["sensor_id"] == sensor_id].iloc[0]
        subsystem = str(row["subsystem"])
        normal_min = float(row["normal_min"])
        normal_max = float(row["normal_max"])

        onset = _find_sensor_onset_by_regression(
            group[["corrected_minute", "value"]].copy(),
            normal_min,
            normal_max,
        )
        if onset is None:
            continue

        if (
            subsystem not in subsystem_onsets
            or onset < subsystem_onsets[subsystem]
        ):
            subsystem_onsets[subsystem] = onset

    # Step 6 — sort by onset minute; return full propagation order
    ordered = sorted(subsystem_onsets, key=lambda s: subsystem_onsets[s])
    return ordered


def _find_sensor_onset_by_regression(
    readings: pd.DataFrame,
    normal_min: float,
    normal_max: float,
) -> float | None:
    """Back-extrapolate the linear cascade trend to find onset.

    Fits a linear regression through the pre-saturation out-of-range
    readings in the main cascade phase, then solves for the minute
    where the regression line crosses the sensor's normal-range
    centre.  Only readings before the first saturation-level reading
    are used; post-plateau noise dips would otherwise pull the slope
    toward zero and push the extrapolated onset far into the past.

    Args:
        readings: DataFrame with columns corrected_minute and value.
        normal_min: Lower bound of the normal operating range.
        normal_max: Upper bound of the normal operating range.

    Returns:
        Estimated physical onset minute, or None if the sensor lacks
        sufficient data for a reliable fit.
    """
    readings = readings.sort_values("corrected_minute", kind="stable")
    normal_center = (normal_min + normal_max) / 2.0
    normal_range = normal_max - normal_min

    # Identify all out-of-range readings
    oor = readings[
        (readings["value"] > normal_max) | (readings["value"] < normal_min)
    ].copy()

    if len(oor) < MIN_REGRESSION_POINTS:
        return None

    # Discard phantom-glitch readings: drop any OOR readings that are
    # separated from later OOR readings by >= PHANTOM_GAP_MINUTES.
    corrected = oor["corrected_minute"].to_numpy(dtype=float)
    gaps = np.diff(corrected)
    large_gap_indices = np.where(gaps >= PHANTOM_GAP_MINUTES)[0]
    if len(large_gap_indices) > 0:
        cascade_start = corrected[large_gap_indices[-1] + 1]
        oor = oor[oor["corrected_minute"] >= cascade_start]

    if len(oor) < MIN_REGRESSION_POINTS:
        return None

    # Determine anomaly direction from the data: most OOR readings
    # above normal_max → deviation goes up; below normal_min → down.
    above = int((oor["value"] > normal_max).sum())
    anomaly_direction = 1 if above > len(oor) // 2 else -1

    # Keep only pre-saturation OOR readings: exclude readings at or
    # beyond the plateau where the deviation has levelled off.
    # Strategy: find the first cascade OOR reading that reaches the
    # saturation level, then discard it and everything after it.
    # This prevents post-plateau noise dips (readings that bounce
    # back below the saturation threshold due to noise or operator
    # suppression) from polluting the regression with near-zero-slope
    # data points far into the cascade.
    saturation_mask = (
        oor["value"] - normal_center
    ).abs() >= SATURATION_FRACTION * normal_range
    if saturation_mask.any():
        first_saturation_minute = float(
            oor.loc[saturation_mask, "corrected_minute"].min()
        )
        linear_oor = oor[oor["corrected_minute"] < first_saturation_minute]
    else:
        linear_oor = oor

    if len(linear_oor) < MIN_REGRESSION_POINTS:
        return None

    # Fit value = slope * corrected_minute + intercept
    slope, intercept = np.polyfit(
        linear_oor["corrected_minute"].to_numpy(dtype=float),
        linear_oor["value"].to_numpy(dtype=float),
        1,
    )

    # Slope must agree with anomaly direction; reject noise artefacts.
    if anomaly_direction * slope <= 0:
        return None

    # Onset: regression line crosses normal_center
    onset = (normal_center - intercept) / slope
    return float(onset)


ANSWER_PY_TEMPLATE = '''def answer() -> list[str]:
    return {result!r}

if __name__ == "__main__":
    import json
    with open("/app/answer.json", "w") as f:
        json.dump(answer(), f, default=list)
'''


if __name__ == "__main__":
    result = solve("/app/dataset")
    Path("/app/answer.py").write_text(ANSWER_PY_TEMPLATE.format(result=result))
    print(f"solved: {result}")
