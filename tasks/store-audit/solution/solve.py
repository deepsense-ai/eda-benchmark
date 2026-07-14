"""Reference solver for the store audit task.

Data cleaning (must happen before crux fixes):
  0a. warehouse_dispatches: drop exact-duplicate rows (July-3 double-log).
  0b. product_catalog: unit_price for Dry products is stored as a
      comma-decimal string ("5,00") — parse to numeric.
  0c. temperature_logs: zone names are inconsistently cased ("frozen",
      "dairy") — normalise to title case.
  0d. temperature_logs: Frozen zone temperature_c uses comma as decimal
      separator — parse to numeric.

Crux fixes:
  1. EAN scanner error: one dispatch row has the kettle's EAN code in
     product_id. Fix: join on ean_code, recover the real product_id.
  2. Refrigerator failure: Frozen and Meat zones spiked above safe
     thresholds on the night of 2023-07-17→18. The 03:17 dispatch is
     disposal, not revenue. Detection: merge_asof maps each dispatch to
     the last temperature reading in its zone — if that reading exceeds
     max_safe_temp_c the dispatch is a disposal write-off.
"""
import pandas as pd


def solve(data_folder: str) -> int:
    # read data
    catalog = pd.read_csv(f"{data_folder}/product_catalog.csv")
    dispatches = pd.read_csv(
        f"{data_folder}/warehouse_dispatches.csv",
        parse_dates=["timestamp"],
    )
    temp_logs = pd.read_csv(
        f"{data_folder}/temperature_logs.csv",
        parse_dates=["timestamp"],
    )

    # clean data
    # drop exact-duplicate dispatch rows
    dispatches = dispatches.drop_duplicates(
        subset=["timestamp", "product_id", "quantity", "total_weight_kg"]
    ).reset_index(drop=True)

    # parse unit_price (Dry products stored as "X,00")
    catalog["unit_price"] = pd.to_numeric(
        catalog["unit_price"].astype(str).str.replace(",", ".", regex=False),
        errors="coerce",
    )

    # normalise zone names to title case
    temp_logs["zone"] = temp_logs["zone"].str.strip().str.title()

    # parse temperature_c (Frozen zone uses comma decimal)
    temp_logs["temperature_c"] = pd.to_numeric(
        temp_logs["temperature_c"]
        .astype(str)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    )

    # Fix Crux 1: EAN scanned into product_id field
    ean_mask = ~dispatches["product_id"].isin(catalog["product_id"])
    ean_to_pid = catalog.set_index(catalog["ean_code"].astype(str))[
        "product_id"
    ]
    dispatches.loc[ean_mask, "product_id"] = dispatches.loc[
        ean_mask, "product_id"
    ].map(ean_to_pid)

    # Fix Crux 2: disposal = dispatch when zone temp exceeded safe limit
    dispatches = (
        dispatches.merge(
            catalog[
                [
                    "product_id",
                    "storage_category",
                    "unit_price",
                    "max_safe_temp_c",
                ]
            ],
            on="product_id",
            how="left",
        )
        .sort_values("timestamp", kind="stable")
        .reset_index(drop=True)
    )

    temp_sorted = temp_logs.sort_values("timestamp", kind="stable").rename(
        columns={
            "zone": "storage_category",
            "temperature_c": "zone_temp_at_dispatch",
        }
    )

    dispatches = pd.merge_asof(
        dispatches,
        temp_sorted[["timestamp", "storage_category", "zone_temp_at_dispatch"]],
        on="timestamp",
        by="storage_category",
        direction="backward",
    )

    dispatches["is_spoilage"] = (
        dispatches["zone_temp_at_dispatch"] > dispatches["max_safe_temp_c"]
    )

    # Compute output
    dispatches["line_value"] = dispatches["unit_price"] * dispatches["quantity"]

    expected_revenue = int(
        dispatches.loc[~dispatches["is_spoilage"], "line_value"].sum()
    )

    return expected_revenue


ANSWER_PY_TEMPLATE = '''def answer() -> int:
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
    print(f"solved: {result}")
