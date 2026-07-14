# Hospital Compensation Registry

****Task:****
You are given database of a hospital compensation registry.
There are some insurance claims, and some people that didn't file any claims yet.
Return a set of three patient IDs that are most likely to be deceased.

****Dataset:****
To access the dataset use the files:
- /app/dataset/hospital_compensation_registry.csv

****Validation:****
Your final answer will be evaluated with the function in this snippet:

```python
def calculate_jaccard_index(answer: Iterable, gt: Iterable) -> float:
    """Calculates the Jaccard index given two iterables:
    ground truth and answer.

    Args:
        gt: An iterable representing the ground truth values.
        answer: An iterable representing the predicted values.

    Returns:
        The Jaccard index as a float.
    """
    gt_set = set(gt)
    answer_set = set(answer)
    tp = len(gt_set & answer_set)
    denom = len(gt_set | answer_set)
    return 0.0 if denom == 0 else tp / denom
```

****Answer format:****
Write your answer as a Python file at `/app/answer.py` that defines an `answer()` function
and, when executed, saves the returned value as JSON to `/app/answer.json`:

```python
def answer() -> set[str]:
    return {"PAT_001", "PAT_002", "PAT_003"}

if __name__ == "__main__":
    import json
    with open("/app/answer.json", "w") as f:
        json.dump(answer(), f, default=list)
```

Before you finish, run `python /app/answer.py` so that both `/app/answer.py` and
`/app/answer.json` exist. The `/app/answer.json` file is what gets graded (sets are
serialized as JSON lists; the verifier converts them back before scoring).
