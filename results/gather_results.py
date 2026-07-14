import argparse
from pathlib import Path

import numpy as np
import pandas as pd

OPENCODE_ALLOWED_MODELS = ["deepseek-reasoner"]


def load_results() -> pd.DataFrame:
    TASK_DIR = Path("../tasks")

    task_names: list[str] = [p.name for p in TASK_DIR.iterdir() if p.is_dir()]

    dfs: list[pd.DataFrame] = []
    for task_name in task_names:
        df: pd.DataFrame = pd.read_csv(TASK_DIR / task_name / "results.csv")
        df["task"] = task_name
        dfs.append(df)
        print(f"Found task: {task_name}")
    return pd.concat(dfs, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create reliability-adjusted and mean-score CSV files per model.")
    parser.add_argument(
        "--ras-output",
        default="ras_results.csv",
        help="Reliability-adjusted results CSV path (default: ras_results.csv)",
    )
    parser.add_argument(
        "--mean-output",
        default="mean_results.csv",
        help="Mean-score results CSV path (default: mean_results.csv)",
    )
    parser.add_argument(
        "-n",
        "--runs",
        type=int,
        default=5,
        help="Expected number of runs per model + agent + task combination",
    )
    args = parser.parse_args()

    results = load_results()

    # remove model name prefix
    results["model_name"] = results["model_name"].str.split("/").str[-1]

    # exclude opencode results, except for allowed models
    results: pd.DataFrame = results[
        (results.agent_name != "opencode") | (results.model_name.isin(OPENCODE_ALLOWED_MODELS))
        ]

    # Ignore trials that did not receive a score.
    results = results.dropna(subset=["reward"]).fillna(0)

    def agg_metrics(g: pd.DataFrame) -> pd.Series:
        ms: float = g["reward"].mean()
        cv: float = g["reward"].std() / ms if ms != 0 else np.nan
        return pd.Series({
            "n": len(g),
            "ms": ms,
            "cv": cv,
            "reliability_adjusted_score": ms * np.exp(-2.25 * cv ** 0.88),
            "mean_duration_sec": g["duration_sec"].mean(),
            "mean_cost_usd": g["cost_usd"].mean(),
        })

    results_grouped: pd.DataFrame = (
        results
        .groupby(
            ["model_name", "agent_name", "reasoning_effort", "task"],
            dropna=False,
        )
        .apply(agg_metrics, include_groups=False)
        .reset_index()
    )

    if results_grouped["n"].nunique() != 1 or results_grouped["n"].iloc[0] != args.runs:
        expected_n = args.runs
        missing = results_grouped[results_grouped["n"] != expected_n].copy()
        missing["missing_runs"] = expected_n - missing["n"]

        error_lines = [
            f"Expected {expected_n} runs for each model + agent + task combination.",
            "Unexpected run counts:",
        ]
        for task_name, task_rows in missing.groupby("task", sort=True):
            error_lines.append(f"{task_name}:")
            for row in task_rows.sort_values("model_name").itertuples(index=False):
                error_lines.append(
                    f"  {row.model_name}: {int(row.missing_runs)}"
                )

        raise ValueError("\n".join(error_lines))

    results_per_model: pd.DataFrame = (
        results_grouped
        .groupby("model_name", as_index=False)
        .agg(
            score=("reliability_adjusted_score", "mean"),
            coefficient_of_variation=("cv", "mean"),
            mean_score=("ms", "mean"),
        )
        .rename(columns={"model_name": "model"})
    )
    ras_results = results_per_model[
        ["model", "score", "coefficient_of_variation"]
    ].rename(
        columns={
            "coefficient_of_variation": "Coefficient of variation",
        }
    )
    ras_results["score"] = ras_results["score"].round(2)
    ras_results["Coefficient of variation"] = (
        ras_results["Coefficient of variation"].round(4)
    )
    ras_results.sort_values(
        "score",
        inplace=True,
        ascending=False,
    )
    ras_results.to_csv(args.ras_output, index=False)

    mean_results = results_per_model[
        ["model", "mean_score"]
    ].rename(columns={"mean_score": "score"})
    mean_results["score"] = mean_results["score"].round(2)
    mean_results.sort_values(
        "score",
        inplace=True,
        ascending=False,
    )
    mean_results.to_csv(args.mean_output, index=False)

    print(f"Reliability-adjusted results saved to {args.ras_output}")
    print(f"Mean results saved to {args.mean_output}")


if __name__ == "__main__":
    main()
