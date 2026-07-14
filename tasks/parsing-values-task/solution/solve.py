"""Reference solver for the parsing values task."""
import os
import re

import numpy as np
import pandas as pd


def solve(data_folder: str) -> list[str]:
    input_csv = "data.csv"

    def parse_event_time(s):
        if pd.isna(s):
            return pd.NaT
        t = str(s).strip()
        if t == "":
            return pd.NaT
        return pd.to_datetime(t, errors="coerce", utc=True)

    def _parse_signed_dirty_number(
        s, *, empty_value, neg_token, removable_tokens
    ):
        if pd.isna(s):
            return empty_value

        raw = str(s).strip()
        if raw == "":
            return empty_value

        neg = False

        if re.search(
            rf"(?<![A-Za-z0-9]){re.escape(neg_token)}(?![A-Za-z0-9])",
            raw,
            flags=re.IGNORECASE,
        ):
            neg = True

        if "(" in raw and ")" in raw:
            neg = True

        cleaned = raw

        for tok in removable_tokens:
            cleaned = re.sub(
                rf"(?<![A-Za-z0-9]){re.escape(tok)}(?![A-Za-z0-9])",
                " ",
                cleaned,
                flags=re.IGNORECASE,
            )

        cleaned = re.sub(r"[A-Za-z\s]+", "", cleaned)
        cleaned = re.sub(r"[^0-9,.\-]", "", cleaned)
        cleaned = re.sub(r"(?<!^)-", "", cleaned)

        if cleaned in {"", "-", ".", ",", "-.", "-,"}:
            return empty_value

        has_comma = "," in cleaned
        has_dot = "." in cleaned

        if has_comma and has_dot:
            last_comma = cleaned.rfind(",")
            last_dot = cleaned.rfind(".")
            if last_dot > last_comma:
                dec_sep = "."
                thou_sep = ","
            else:
                dec_sep = ","
                thou_sep = "."
            numeric = cleaned.replace(thou_sep, "").replace(dec_sep, ".")
        elif has_comma:
            idx = cleaned.rfind(",")
            digits_after = len(cleaned) - idx - 1
            numeric = (
                cleaned.replace(",", ".")
                if digits_after == 2
                else cleaned.replace(",", "")
            )
        elif has_dot:
            idx = cleaned.rfind(".")
            digits_after = len(cleaned) - idx - 1
            numeric = cleaned if digits_after == 2 else cleaned.replace(".", "")
        else:
            numeric = cleaned

        if numeric in {"", "-", "."}:
            return empty_value

        val = float(numeric)

        if neg:
            val = -abs(val)

        return val

    def parse_amount(s):
        return _parse_signed_dirty_number(
            s,
            empty_value=np.nan,
            neg_token="CR",
            removable_tokens=["C1", "C2"],
        )

    def parse_notes(s):
        if pd.isna(s):
            return None, 0.0, 0.0, False

        text = str(s).strip()
        if text == "":
            return None, 0.0, 0.0, False

        m_items = re.search(
            r"\bitems\s*=\s*([0-9]+)\b", text, flags=re.IGNORECASE
        )
        items = int(m_items.group(1)) if m_items else None

        m_adj = re.search(
            r"\badj\s*=\s*([+\-]?\d+(?:\.\d+)?)\s*%", text, flags=re.IGNORECASE
        )
        adj_pct = float(m_adj.group(1)) / 100.0 if m_adj else 0.0

        m_fee = re.search(
            r"\bfee\s*=\s*([+\-]?\d+(?:\.\d+)?)\b", text, flags=re.IGNORECASE
        )
        fee = float(m_fee.group(1)) if m_fee else 0.0

        waive = bool(
            re.search(r"\bwaive\s*=\s*true\b", text, flags=re.IGNORECASE)
        )

        return items, adj_pct, fee, waive

    def add_robust_z(group: pd.DataFrame) -> pd.DataFrame:
        x = group["_net"].to_numpy(dtype=float)
        med = np.median(x)
        mad = np.median(np.abs(x - med))

        out = group.copy()
        if mad == 0 or not np.isfinite(mad):
            out["_robust_z"] = 0.0
        else:
            out["_robust_z"] = 0.6745 * (x - med) / mad
        return out

    def solve_in(csv_path=input_csv):
        if csv_path is None:
            raise ValueError("csv_path is None")

        csv_path = str(csv_path)

        if os.path.isdir(csv_path):
            csv_path = os.path.join(csv_path, "data.csv")

        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        df = pd.read_csv(csv_path)

        df["_row_order"] = np.arange(len(df), dtype=int)

        df["_event_time"] = df["event_time"].apply(parse_event_time)
        df["_base_amount"] = df["amount_str"].apply(parse_amount)

        parsed_notes = df["notes"].apply(parse_notes)
        df["_items"] = parsed_notes.apply(lambda x: x[0])
        df["_adj_pct"] = parsed_notes.apply(lambda x: x[1])
        df["_fee"] = parsed_notes.apply(lambda x: x[2])
        df["_waive"] = parsed_notes.apply(lambda x: x[3])

        df["_net"] = df["_base_amount"] * (1.0 + df["_adj_pct"]) + df["_fee"]

        df.loc[df["_waive"], "_net"] = 0.0
        df.loc[df["_base_amount"].isna(), "_net"] = np.nan

        min_ts = pd.Timestamp("1900-01-01 00:00:00", tz="UTC")
        df["_event_sort"] = df["_event_time"].fillna(min_ts)
        df["_net_present"] = np.isfinite(
            df["_net"].to_numpy(dtype=float)
        ).astype(int)

        df = df.sort_values(
            by=["record_id", "_event_sort", "_net_present", "_row_order"],
            ascending=[True, False, False, True],
            kind="mergesort",
        )
        df = df.drop_duplicates(subset=["record_id"], keep="first").copy()

        q4_start = pd.Timestamp("2025-10-01 00:00:00", tz="UTC")
        q4_end = pd.Timestamp("2025-12-31 23:59:59", tz="UTC")

        mask = (
            df["_event_time"].notna()
            & (df["_event_time"] >= q4_start)
            & (df["_event_time"] <= q4_end)
            & (df["channel"].astype(str).str.lower() != "phone")
            & df["_net"].notna()
            & np.isfinite(df["_net"].to_numpy(dtype=float))
        )

        cand = df.loc[mask].copy()

        cand["_month"] = cand["_event_time"].dt.strftime("%Y-%m")
        cand["_items_eff"] = cand["_items"].fillna(1).clip(lower=1)

        cand = cand.groupby(["region", "_month"], group_keys=False).apply(
            add_robust_z
        )

        cand["_abs_robust_z"] = cand["_robust_z"].abs()
        cand["_anomaly_score"] = cand["_abs_robust_z"] * np.log1p(
            cand["_items_eff"]
        )

        cand = cand.sort_values(
            by=["_anomaly_score", "_abs_robust_z", "_event_time", "record_id"],
            ascending=[False, False, False, True],
            kind="mergesort",
        )

        return cand.head(10)["record_id"].tolist()

    return solve_in(data_folder)


ANSWER_PY_TEMPLATE = '''def answer() -> list[str]:
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
