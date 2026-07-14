"""Reference solver for the cleaning service task."""
import json

import pandas as pd


def solve(data_folder: str) -> dict[str, list[int]]:
    # Read timesheet and tasks data
    df_raw = pd.read_csv(
        f"{data_folder}/timesheet.csv", dtype={"employee_id": str}
    )

    # Remove technical row identifier before detecting duplicates
    if "id" in df_raw.columns:
        df_raw = df_raw.drop(columns=["id"])

    # Remove exact duplicate rows after ignoring id
    df_raw = df_raw.drop_duplicates().reset_index(drop=True)

    tasks_df = pd.read_csv(f"{data_folder}/tasks.csv")
    employees_df = pd.read_csv(
        f"{data_folder}/employees.csv", dtype={"PESEL": str}
    )

    # Keep only employee IDs that exist in employees.csv
    valid_employee_ids = set(
        employees_df["PESEL"].astype(str).str.strip().str.zfill(11)
    )

    # Enforce 11-digit employee_id and validate against employees.csv
    df_raw["employee_id"] = (
        df_raw["employee_id"].astype(str).str.strip().str.zfill(11)
    )
    valid_mask = df_raw["employee_id"].str.fullmatch(r"\d{11}") & df_raw[
        "employee_id"
    ].isin(valid_employee_ids)
    df_filtered = df_raw[valid_mask].copy()

    # Convert date column and reject non-existing dates
    df_filtered["date"] = pd.to_datetime(
        df_filtered["date"], format="%Y-%m-%d", errors="coerce"
    )
    df_filtered = df_filtered[df_filtered["date"].notna()].copy()

    # Filter out rows where no hours were worked
    df_filtered = pd.DataFrame(
        df_filtered[df_filtered["hours_worked"] != 0].copy()
    )

    # Recalculate bonus based on pay_per_completion
    tasks_dict = {
        int(row["task_id"]): float(row["pay_per_completion"])
        for _, row in tasks_df.iterrows()
    }
    df_filtered["performed_tasks"] = df_filtered["performed_tasks"].astype(str)

    def calculate_bonus(tasks_str: str) -> float:
        tasks_text = str(tasks_str).strip()

        if not tasks_text or tasks_text.lower() == "nan":
            return 0.0

        # Fix missing opening bracket
        if not tasks_text.startswith("[") and tasks_text.endswith("]"):
            tasks_text = "[" + tasks_text

        # Fix missing closing bracket
        if tasks_text.startswith("[") and not tasks_text.endswith("]"):
            tasks_text = tasks_text + "]"

        try:
            tasks_done: list[int] = json.loads(tasks_text)
        except (TypeError, json.JSONDecodeError):
            return 0.0

        return sum(tasks_dict.get(int(t), 0) for t in tasks_done)

    df_filtered["bonus"] = df_filtered["performed_tasks"].apply(calculate_bonus)

    # Add columns for grouping and filtering
    df_filtered["year_month"] = (
        df_filtered["date"].dt.to_period("M").astype(str)
    )
    df_filtered["weekday"] = df_filtered["date"].dt.weekday

    # Find first Tuesday of each month
    tuesdays = df_filtered[df_filtered["weekday"] == 1].copy()
    first_tuesday_per_month = tuesdays.groupby("year_month", as_index=False)[
        "date"
    ].min()
    first_tuesday_per_month = pd.DataFrame(first_tuesday_per_month).rename(
        columns={"date": "billing_start_date"}
    )

    first_tuesday_per_month = pd.DataFrame(first_tuesday_per_month)
    first_tuesday_per_month["billing_month"] = first_tuesday_per_month[
        "year_month"
    ]

    # Assign each row to correct billing period
    billing_starts = pd.DataFrame(
        first_tuesday_per_month[["billing_start_date", "billing_month"]]
    )
    billing_starts = billing_starts.sort_values(
        "billing_start_date", kind="stable"
    )

    df_filtered_sorted = df_filtered.sort_values("date", kind="stable")

    df_billed = pd.merge_asof(
        df_filtered_sorted,
        billing_starts,
        left_on="date",
        right_on="billing_start_date",
        direction="backward",
    )
    df_billed = df_billed[df_billed["billing_month"].notna()].reset_index(
        drop=True
    )

    # Aggregate salary and bonuses per employee per billing_month
    summary = df_billed.groupby(
        ["billing_month", "employee_id"], as_index=False
    ).agg(
        salary_last=pd.NamedAgg(column="salary_amount", aggfunc="last"),
        bonus_sum=pd.NamedAgg(column="bonus", aggfunc="sum"),
    )
    summary = summary.assign(
        total_salary=summary["salary_last"] + summary["bonus_sum"]
    )

    # Prepare final result
    # month -> list of employee salaries sorted by employee_id ascending
    result: dict[str, list[int]] = {}

    summary_sorted = summary.sort_values(
        ["employee_id", "billing_month"], kind="stable"
    )

    for employee_id, group in summary_sorted.groupby("employee_id"):
        result[str(employee_id)] = [
            int(row["total_salary"]) for _, row in group.iterrows()
        ]

    return result


ANSWER_PY_TEMPLATE = '''def answer() -> dict[str, list[int]]:
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
    print(f"solved: {len(result)} employees")
