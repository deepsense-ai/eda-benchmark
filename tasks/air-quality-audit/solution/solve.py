"""Reference solver for the air quality audit task."""
import os

import pandas as pd


def _load_data(data_folder: str) -> pd.DataFrame:
    stations = pd.read_csv(os.path.join(data_folder, "stations.csv"))

    readings = pd.read_csv(
        os.path.join(data_folder, "readings.csv"),
        parse_dates=["timestamp"],
    )

    weather = pd.read_csv(
        os.path.join(data_folder, "weather_readings.csv"),
        parse_dates=["timestamp"],
    )

    weather_profile = weather.groupby(
        ["district", "timestamp"], as_index=False
    ).agg(
        humidity_pct=("humidity_pct", "mean"),
        temperature_c=("temperature_c", "mean"),
        wind_speed_m_s=("wind_speed_m_s", "mean"),
        rain_accumulation_mm=("rain_accumulation_mm", "mean"),
    )

    df = readings.merge(
        stations[["station_id", "district"]],
        on="station_id",
        how="left",
    )

    df = df.merge(
        weather_profile,
        on=["district", "timestamp"],
        how="left",
    )

    return df


def _fill_missing_readings(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(
        ["station_id", "pollutant", "timestamp"], kind="stable"
    ).copy()

    df["current_reading"] = df.groupby(["station_id", "pollutant"], sort=False)[
        "current_reading"
    ].transform(lambda series: series.interpolate(limit_direction="both"))

    return df


def _safe_corr(left: pd.Series, right: pd.Series) -> float:
    pair = pd.concat([left, right], axis=1).dropna()

    if len(pair) < 3:
        return 0.0

    corr = pair.iloc[:, 0].corr(pair.iloc[:, 1])
    return 0.0 if pd.isna(corr) else float(corr)


def _add_peer_context(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["station_id", "timestamp"], kind="stable").copy()
    group = ["district", "pollutant", "timestamp"]

    df["peer_median"] = df.groupby(group)["current_reading"].transform("median")
    df["residual"] = df["current_reading"] - df["peer_median"]

    return df


def _station_features(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for station_id, station_df in df.groupby("station_id", sort=False):
        station_df = station_df.sort_values(
            "timestamp", kind="stable"
        ).reset_index(drop=True)

        reading = station_df["current_reading"]
        peer = station_df["peer_median"]
        residual = station_df["residual"]

        humidity = station_df["humidity_pct"]
        wind = station_df["wind_speed_m_s"]
        rain = station_df["rain_accumulation_mm"]

        same_time_corr = _safe_corr(reading, peer)
        previous_peer_corr = _safe_corr(reading, peer.shift(1))
        diff_corr = _safe_corr(reading.diff(), peer.diff())
        previous_diff_corr = _safe_corr(reading.diff(), peer.diff().shift(1))

        reading_delta_std = reading.diff().std(ddof=0)
        peer_delta_std = peer.diff().std(ddof=0)

        reading_iqr = reading.quantile(0.75) - reading.quantile(0.25)
        peer_iqr = peer.quantile(0.75) - peer.quantile(0.25)

        lag_score = previous_peer_corr - same_time_corr

        delta_compression = 1.0 - (
            reading_delta_std / peer_delta_std if peer_delta_std else 1.0
        )

        range_compression = 1.0 - (reading_iqr / peer_iqr if peer_iqr else 1.0)

        compression_score = pd.Series(
            [delta_compression, range_compression]
        ).mean()

        corr_hum = _safe_corr(residual, humidity)
        corr_wind = _safe_corr(residual, wind)
        corr_rain = _safe_corr(residual, rain)
        weather_score = abs(corr_hum) + abs(corr_wind) + abs(corr_rain)

        rows.append(
            {
                "station_id": station_id,
                "same_time_corr": same_time_corr,
                "previous_peer_corr": previous_peer_corr,
                "diff_corr": diff_corr,
                "previous_diff_corr": previous_diff_corr,
                "lag_score": lag_score,
                "delta_variance_score": delta_compression,
                "range_compression": range_compression,
                "compression_score": compression_score,
                "humidity_score": weather_score,
                "weather_score": weather_score,
                "residual_abs_mean": residual.abs().mean(),
            }
        )

    return pd.DataFrame(rows)


def solve(data_folder: str) -> set[str]:
    df = _load_data(data_folder)
    df = _fill_missing_readings(df)
    df = _add_peer_context(df)
    features = _station_features(df)

    features["lag_score"] = (
        features["previous_diff_corr"] - features["diff_corr"]
    )

    lag_candidates = features[features["compression_score"] >= -0.2]
    lag_station = lag_candidates.nlargest(1, "lag_score")["station_id"].iloc[0]
    compression_station = features.nlargest(1, "delta_variance_score")[
        "station_id"
    ].iloc[0]

    weather_threshold = features["weather_score"].quantile(0.9)
    weather_candidates = features[
        features["weather_score"] >= weather_threshold
    ].copy()

    weather_candidates = weather_candidates[
        ~weather_candidates["station_id"].isin(
            {lag_station, compression_station}
        )
    ]

    if weather_candidates.empty:
        weather_candidates = features[
            ~features["station_id"].isin({lag_station, compression_station})
        ]

    weather_station = weather_candidates.nlargest(1, "weather_score")[
        "station_id"
    ].iloc[0]

    return {lag_station, compression_station, weather_station}


ANSWER_PY_TEMPLATE = '''def answer() -> set[str]:
    return {result!r}

if __name__ == "__main__":
    import json
    with open("/app/answer.json", "w") as f:
        json.dump(answer(), f, default=list)
'''


if __name__ == "__main__":
    from pathlib import Path

    result = solve("/app/dataset")
    Path("/app/answer.py").write_text(ANSWER_PY_TEMPLATE.format(result=result))
    print(f"solved: {sorted(result)}")
