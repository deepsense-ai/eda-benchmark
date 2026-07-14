"""Grade /app/answer.json against the ground-truth solution string.

Sets arrive serialized as lists and are converted back
based on the expected type before scoring. Prints exactly one float (the
reward) to stdout; all diagnostics go to stderr. Never raises — any invalid
answer scores 0.0.
"""

import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scoring import (
    calculate_dict_of_ints_score,
    calculate_dict_of_lists_score,
    calculate_dict_of_sets_score,
    calculate_int_score,
    calculate_jaccard_index,
    calculate_jaccard_index_with_order_factor,
    calculate_order_score,
)

ANSWER_PATH = Path("/app/answer.json")
CONFIG_PATH = Path(__file__).parent / "config.json"


def _as_int(value):
    """JSON has one number type; accept integral floats as ints."""
    if isinstance(value, bool):
        raise ValueError(f"expected an integer, got {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError(f"expected an integer, got {value!r}")


def _as_list(value):
    if not isinstance(value, list):
        raise ValueError(f"expected a list, got {type(value).__name__}")
    return value


def _as_dict(value):
    if not isinstance(value, dict):
        raise ValueError(f"expected a dict, got {type(value).__name__}")
    return value


def _score(evaluator_type: str, answer, gt_str: str) -> float:
    if evaluator_type == "$int":
        return calculate_int_score(_as_int(answer), int(gt_str))
    if evaluator_type == "$set":
        return calculate_jaccard_index(set(_as_list(answer)), ast.literal_eval(gt_str))
    if evaluator_type == "$list":
        return calculate_jaccard_index_with_order_factor(
            _as_list(answer), list(ast.literal_eval(gt_str))
        )
    if evaluator_type == "$list_permutation":
        return calculate_order_score(_as_list(answer), list(ast.literal_eval(gt_str)))
    if evaluator_type == "$dict_of_ints":
        answer = {k: _as_int(v) for k, v in _as_dict(answer).items()}
        return calculate_dict_of_ints_score(answer, dict(ast.literal_eval(gt_str)))
    if evaluator_type == "$dict_of_sets":
        answer = {k: set(_as_list(v)) for k, v in _as_dict(answer).items()}
        return calculate_dict_of_sets_score(answer, dict(ast.literal_eval(gt_str)))
    if evaluator_type == "$dict_of_lists":
        answer = {k: _as_list(v) for k, v in _as_dict(answer).items()}
        return calculate_dict_of_lists_score(answer, dict(ast.literal_eval(gt_str)))
    raise ValueError(f"unknown evaluator type: {evaluator_type}")


def main() -> float:
    solution = json.loads(CONFIG_PATH.read_text())["solution"].strip()

    # Longest prefixes first so e.g. $list_permutation wins over $list.
    known_types = sorted(
        ["$int", "$set", "$list", "$list_permutation",
         "$dict_of_ints", "$dict_of_sets", "$dict_of_lists"],
        key=len, reverse=True,
    )
    evaluator_type = next(
        (t for t in known_types if solution.startswith(t + ":")), None
    )
    if evaluator_type is None:
        raise ValueError(f"solution string has no known prefix: {solution[:40]}")
    gt_str = solution[len(evaluator_type) + 1:].strip()

    if not ANSWER_PATH.exists():
        print(f"answer file not found: {ANSWER_PATH}", file=sys.stderr)
        return 0.0
    try:
        answer = json.loads(ANSWER_PATH.read_text())
    except (ValueError, UnicodeDecodeError) as e:
        print(f"failed to parse {ANSWER_PATH}: {e}", file=sys.stderr)
        return 0.0

    try:
        return float(_score(evaluator_type, answer, gt_str))
    except (ValueError, TypeError) as e:
        print(f"scoring failed: {e}", file=sys.stderr)
        return 0.0


if __name__ == "__main__":
    print(main())
