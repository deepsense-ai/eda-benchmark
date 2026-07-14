"""Reference solver for the solar farm daily yield task."""
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

REPORT_DAY = pd.Timestamp("2024-03-15", tz="UTC")
WINDOW_START_UTC = REPORT_DAY
WINDOW_END_UTC = REPORT_DAY + pd.Timedelta(days=1)

ENERGY_TO_KWH = {
    "KWH": 1.0,
    "MWH": 1000.0,
    "WH": 0.001,
    "BTU": 1.0 / 3412.142,
}


def _load_farms_with_id(data_folder: Path) -> pd.DataFrame:
    farms = pd.read_csv(data_folder / "farms.csv")
    registry = pd.read_csv(data_folder / "farm_registry.csv")
    farms["join_key"] = farms["farm_name"].str.strip().str.lower()
    registry["join_key"] = registry["farm_name"].str.strip().str.lower()
    return farms.merge(registry, on="join_key", how="left")


def _load_maintenance_windows_utc(
    data_folder: Path, tz_map: dict, name_to_id: dict
) -> dict:
    notes = (data_folder / "maintenance_notes.txt").read_text(encoding="utf-8")
    windows = {}
    sentences = re.split(r"\.\s+|\n+", notes)
    for sentence in sentences:
        if "COMPLETED" not in sentence:
            continue
        farm_id = next(
            (
                fid
                for name, fid in name_to_id.items()
                if name.strip().lower() in sentence.lower()
            ),
            None,
        )
        if not farm_id:
            continue
        day_match = re.search(
            r"(?:March\s+(\d{2})|(\d{2})th\s+of\s+March)", sentence
        )
        time_match = re.findall(r"(\d{2}:\d{2})", sentence)
        if day_match and len(time_match) >= 2:
            day = day_match.group(1) or day_match.group(2)
            tz = tz_map[farm_id]
            start_utc = (
                pd.Timestamp(f"2024-03-{day} {time_match[0]}")
                .tz_localize(tz)
                .tz_convert("UTC")
            )
            end_utc = (
                pd.Timestamp(f"2024-03-{day} {time_match[1]}")
                .tz_localize(tz)
                .tz_convert("UTC")
            )
            windows.setdefault(farm_id, []).append((start_utc, end_utc))
    return windows


def _read_production_csv(path: Path) -> pd.DataFrame:
    with path.open("rb") as f:
        magic = f.read(2)
        encoding = "utf-16" if magic in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    with path.open(encoding=encoding) as f:
        for _ in range(3):
            f.readline()
        line = f.readline()
        sep = ";" if ";" in line else ","
    df = pd.read_csv(path, sep=sep, encoding=encoding, skiprows=3)
    df = df.rename(columns={"timestamp\t": "timestamp"})

    def parse_numeric(val: Any) -> Any:
        if pd.isna(val):
            return val
        if isinstance(val, (int, float)):
            return val
        val_str = str(val).strip()
        if sep == ";" and "," in val_str:
            val_str = val_str.replace(".", "").replace(",", ".")
        try:
            return float(val_str)
        except ValueError:
            return val

    for c in df.columns:
        if c != "timestamp":
            df[c] = df[c].apply(parse_numeric)
    return df


def _parse_mixed_timestamps(s: pd.Series) -> pd.Series:
    iso = pd.to_datetime(s, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    fallback = pd.to_datetime(s, format="%d.%m.%Y %H:%M:%S", errors="coerce")
    return iso.fillna(fallback)


def _process_farm(
    data_folder: Path,
    farm_id: str,
    tz: str,
    unit: str,
    reading_type: str,
    offset: float,
    col: str,
    maint: list,
) -> int:
    df = _read_production_csv(data_folder / f"production_{farm_id}.csv")
    df["utc_ts"] = (
        _parse_mixed_timestamps(df["timestamp"])
        .dt.tz_localize(tz)
        .dt.tz_convert("UTC")
    )
    df = df.dropna(subset=["utc_ts"])
    df = df.drop_duplicates(subset=["utc_ts"], keep="last")
    df = df.sort_values(by="utc_ts", kind="stable")
    df = df[
        (df["utc_ts"] >= WINDOW_START_UTC) & (df["utc_ts"] < WINDOW_END_UTC)
    ]
    df["temp"] = pd.to_numeric(df["inverter_temperature_C"], errors="coerce")
    spikes = df[df["temp"] > 85.0]["utc_ts"]
    for spike_time in spikes:
        df = df[
            ~(
                (df["utc_ts"] >= spike_time)
                & (df["utc_ts"] <= spike_time + pd.Timedelta(minutes=45))
            )
        ]
    df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=[col])
    df = df[df[col] != -999.0]
    for start, end in maint:
        df = df[~((df["utc_ts"] >= start) & (df["utc_ts"] < end))]
    corrected = df[col] - offset
    if reading_type == "power":
        tdiff = df["utc_ts"].diff().shift(-1).dt.total_seconds() / 3600.0
        tdiff = tdiff.fillna(tdiff.median())
        total = sum(v * dt for v, dt in zip(corrected, tdiff))
    else:
        total = sum(v * ENERGY_TO_KWH[unit.upper()] for v in corrected)
    return int(round(total))


def solve(data_folder: str) -> dict[str, int]:
    folder = Path(data_folder)
    meta = _load_farms_with_id(folder)
    with (folder / "sensors_calibration.json").open() as f:
        raw_calib = json.load(f)
        sys_conf = raw_calib["enterprise_platform"]["deployment_environments"]
        calib = sys_conf["system_config"]["farms"]
    tz_map = dict(zip(meta["farm_id"], meta["timezone"]))
    name_to_id = dict(zip(meta["farm_name_x"], meta["farm_id"]))
    maint = _load_maintenance_windows_utc(folder, tz_map, name_to_id)
    return {
        fid: _process_farm(
            folder,
            fid,
            tz_map[fid],
            calib[fid]["sensor_info"]["unit"],
            calib[fid]["sensor_info"]["reading_type"],
            calib[fid]["calibration_data"]["calibration_offset"],
            calib[fid]["calibration_data"]["value_column_name"],
            maint.get(fid, []),
        )
        for fid in meta["farm_id"]
    }


ANSWER_PY_TEMPLATE = '''def answer() -> dict[str, int]:
    return {result!r}

if __name__ == "__main__":
    import json
    with open("/app/answer.json", "w") as f:
        json.dump(answer(), f, default=list)
'''


if __name__ == "__main__":
    result = solve("/app/dataset")
    Path("/app/answer.py").write_text(ANSWER_PY_TEMPLATE.format(result=result))
    print(f"solved: {len(result)} farms")
