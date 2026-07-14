#!/usr/bin/env python3
"""Render a per-trial job report from Harbor result files."""

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import click
import numpy as np

CSV_FILENAME = "results.csv"
CSV_HEADER = [
    "model_name",
    "agent_name",
    "reasoning_effort",
    "started_at",
    "trial_id",
    "reward",
    "duration_sec",
    "cost_usd",
]


@click.command()
@click.argument(
    "job_dir",
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        path_type=Path,
    ),
)
def main(job_dir: Path) -> None:
    """Render a per-trial reward and timing summary for JOB_DIR."""
    render_report(job_dir.resolve())


@dataclass
class TrialRow:
    task_name: str
    run_name: str
    model_name: str
    agent_name: str
    reasoning_effort: str
    started_at: str | None
    reward: float | int | None
    duration_sec: float | None
    cost_usd: float | None


@dataclass
class JobConfig:
    task_paths: list[str]
    agents: list[dict]


def _load_config(job_dir: Path) -> JobConfig | None:
    config_path = job_dir / "config.json"
    if not config_path.exists():
        return None
    data = json.loads(config_path.read_text())
    tasks = [t.get("path") or t.get("name") or "?" for t in data.get("tasks", [])]
    agents = data.get("agents", [])
    return JobConfig(task_paths=tasks, agents=agents)


def _format_config_header(config: JobConfig) -> str:
    lines = []

    tasks_str = ", ".join(config.task_paths) if config.task_paths else "-"
    lines.append(f"  Tasks:  {tasks_str}")

    for agent in config.agents:
        parts = []
        if name := agent.get("name"):
            parts.append(f"agent={name}")
        if model := agent.get("model_name"):
            parts.append(f"model={model}")
        kwargs = agent.get("kwargs") or {}
        if effort := kwargs.get("reasoning_effort"):
            parts.append(f"reasoning_effort={effort}")
        lines.append(f"  Agent:  {' | '.join(parts)}")

    return "\n".join(lines)


def _extract_config_agent_metadata(agent: dict) -> tuple[str, str, str]:
    kwargs = agent.get("kwargs") or {}

    model_name = str(agent.get("model_name") or "")
    agent_name = str(agent.get("name") or "")
    reasoning_effort = str(
        kwargs.get("reasoning_effort")
        or agent.get("reasoning_effort")
        or "default"
    )

    return model_name, agent_name, reasoning_effort


def _extract_agent_info_metadata(agent_info: dict) -> tuple[str, str, str]:
    model_info = agent_info.get("model_info")
    model_name = ""
    if isinstance(model_info, dict):
        model_name = str(
            model_info.get("model_name")
            or model_info.get("name")
            or model_info.get("id")
            or ""
        )
    elif model_info:
        model_name = str(model_info)

    agent_name = str(agent_info.get("name") or "")
    reasoning_effort = str(agent_info.get("reasoning_effort") or "default")

    return model_name, agent_name, reasoning_effort


def _extract_trial_agent_metadata(trial_result: dict) -> tuple[str, str, str]:
    config_agent = (trial_result.get("config") or {}).get("agent")
    if isinstance(config_agent, dict):
        return _extract_config_agent_metadata(config_agent)

    agent_info = trial_result.get("agent_info")
    if isinstance(agent_info, dict):
        return _extract_agent_info_metadata(agent_info)

    return "", "", "default"


def _extract_primary_reward(trial_result: dict) -> float | int | None:
    rewards = ((trial_result.get("verifier_result") or {}).get("rewards") or {})
    if not rewards:
        return None
    if "reward" in rewards:
        return rewards["reward"]
    return next(iter(rewards.values()))


def _extract_trial_started_at(trial_result: dict) -> str | None:
    started_at = trial_result.get("started_at")
    return str(started_at) if started_at else None


def _extract_duration_sec(trial_result: dict) -> float | None:
    started_at = trial_result.get("started_at")
    finished_at = trial_result.get("finished_at")
    if not started_at or not finished_at:
        return None
    return (
        datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)
    ).total_seconds()


def _extract_cost_usd(trial_result: dict) -> float | None:
    agent_result = trial_result.get("agent_result") or {}
    cost = agent_result.get("cost_usd")
    if cost is not None:
        return cost

    step_results = trial_result.get("step_results") or []
    step_costs = [
        step_cost
        for step in step_results
        if (step_cost := ((step.get("agent_result") or {}).get("cost_usd"))) is not None
    ]
    if step_costs:
        return sum(step_costs)
    return None


def _append_to_csv(rows: list[TrialRow]) -> None:
    """Additively append trial rows to tasks/{task_name}/results.csv."""
    rows_by_task: dict[str, list[TrialRow]] = {}
    for row in rows:
        rows_by_task.setdefault(row.task_name, []).append(row)

    for task_name, task_rows in rows_by_task.items():
        csv_path = Path("tasks") / task_name / CSV_FILENAME
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        write_header = not csv_path.exists() or csv_path.stat().st_size == 0
        with csv_path.open("a", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(CSV_HEADER)
            for row in task_rows:
                trial_id = row.run_name
                started_at = row.started_at or ""
                reward = f"{float(row.reward):.6f}" if row.reward is not None else ""
                duration = (
                    f"{row.duration_sec:.3f}" if row.duration_sec is not None else ""
                )
                cost = f"{row.cost_usd:.6f}" if row.cost_usd is not None else ""
                writer.writerow([
                    row.model_name,
                    row.agent_name,
                    row.reasoning_effort,
                    started_at,
                    trial_id,
                    reward,
                    duration,
                    cost,
                ])

        print(f"Appended to {csv_path}")


def _split_trial_name(trial_name: str, task_name: str) -> tuple[str, str]:
    if "__" not in trial_name:
        return task_name, trial_name

    task_part, run_part = trial_name.rsplit("__", 1)
    return task_part, run_part


def _load_trial_rows(job_dir: Path) -> list[TrialRow]:
    trial_rows: list[TrialRow] = []
    for child in sorted(job_dir.iterdir()):
        result_path = child / "result.json"
        if not child.is_dir() or not result_path.exists():
            continue

        trial_result = json.loads(result_path.read_text())
        trial_name = trial_result["trial_name"]
        task_name = trial_result["task_name"]
        task_display, run_name = _split_trial_name(trial_name, task_name)
        model_name, agent_name, reasoning_effort = _extract_trial_agent_metadata(
            trial_result
        )
        trial_rows.append(
            TrialRow(
                task_name=task_display,
                run_name=run_name,
                model_name=model_name,
                agent_name=agent_name,
                reasoning_effort=reasoning_effort,
                started_at=_extract_trial_started_at(trial_result),
                reward=_extract_primary_reward(trial_result),
                duration_sec=_extract_duration_sec(trial_result),
                cost_usd=_extract_cost_usd(trial_result),
            )
        )

    return trial_rows


def _reliability_adjusted_score(scores: np.ndarray) -> float:
    """ms * exp(-2.25 * CV^0.88), where ms=mean, CV=sd/ms."""
    ms = float(np.mean(scores))
    if ms == 0:
        return 0.0
    sd = float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0
    cv = sd / ms
    return ms * np.exp(-2.25 * (cv ** 0.88))


def render_report(job_dir: Path) -> None:
    config = _load_config(job_dir)
    rows = _load_trial_rows(job_dir)
    if not rows:
        raise click.ClickException(f"No trial result files found in {job_dir}")

    _append_to_csv(rows)

    print(f"Job: {job_dir.name}")
    if config:
        print(_format_config_header(config))
    print()

    groups: dict[tuple[str, str, str, str], list[TrialRow]] = {}
    for row in rows:
        group_key = (
            row.task_name,
            row.agent_name,
            row.model_name,
            row.reasoning_effort,
        )
        groups.setdefault(group_key, []).append(row)

    for (
        task_name,
        agent_name,
        model_name,
        reasoning_effort,
    ), group_rows in groups.items():
        # Sort runs within the group by run_name
        group_rows = sorted(group_rows, key=lambda r: r.run_name)

        reward_values = np.array(
            [float(r.reward) for r in group_rows if r.reward is not None],
            dtype=float,
        )
        duration_values = [
            r.duration_sec for r in group_rows if r.duration_sec is not None
        ]

        print(f"Task: {task_name}")
        metadata_parts = []
        if agent_name:
            metadata_parts.append(f"agent={agent_name}")
        if model_name:
            metadata_parts.append(f"model={model_name}")
        if reasoning_effort:
            metadata_parts.append(f"reasoning_effort={reasoning_effort}")
        if metadata_parts:
            print(f"  Agent: {' | '.join(metadata_parts)}")

        for i, row in enumerate(group_rows, start=1):
            reward_str = f"{float(row.reward):.4f}" if row.reward is not None else "-"
            time_str = (
                f"{row.duration_sec / 60:.2f}min"
                if row.duration_sec is not None
                else "-"
            )
            cost_str = (
                f"{row.cost_usd:.3f}" if row.cost_usd is not None else "-"
            )
            print(
                f"    {row.run_name}: {reward_str} | Time: {time_str} | Cost: {cost_str}"
            )

        if len(reward_values) > 0:
            ms = float(np.mean(reward_values))
            sd = float(np.std(reward_values, ddof=1)) if len(reward_values) > 1 else 0.0
            cv = sd / ms if ms != 0 else 0.0
            ras = _reliability_adjusted_score(reward_values)
            avg_time = (
                f"{np.mean(duration_values) / 60:.2f}min" if duration_values else "-"
            )
            cost_values = [
                r.cost_usd for r in group_rows if r.cost_usd is not None
            ]
            total_cost = (
                f"{sum(cost_values):.3f}" if cost_values else "-"
            )
            print(f"    Mean: {ms:.4f}")
            print(f"    Standard deviation: {sd:.4f}")
            print(f"    Coefficient of variation: {cv:.4f}")
            print(f"    Average time: {avg_time}")
            print(f"    Reliability-adjusted score: {ras:.3f}")
            print(f"    Total cost: {total_cost}")

        print()

if __name__ == "__main__":
    main()
