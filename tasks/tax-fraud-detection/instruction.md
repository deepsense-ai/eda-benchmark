# Tax Fraud Detection

****Task:****
You are a tax auditor reviewing company registrations and invoice records.
Your task is to identify companies whose profile or transaction history would merit deeper investigation.

You will be provided with two datasets: one containing company information and another
containing invoice details. Use the available evidence to determine which companies appear most anomalous
relative to the rest of the dataset.

As you review the data, pay attention to patterns that would usually stand out in a forensic audit like:
  a) unusual leading-digit behavior among active sellers,
  b) companies that appear only as buyers despite having weak operating fundamentals, and
  c) sellers whose payments to external recipients look outsized relative to their declared business footprint.

Return a set of **10 company IDs** that are most likely to require investigation.

****Dataset:****
To access the dataset use the files:
- /app/dataset/companies.csv
- /app/dataset/invoices.csv

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
def answer() -> set[int]:
    return {1234, 2137, ...}

if __name__ == "__main__":
    import json
    with open("/app/answer.json", "w") as f:
        json.dump(answer(), f, default=list)
```

Before you finish, run `python /app/answer.py` so that both `/app/answer.py` and
`/app/answer.json` exist. The `/app/answer.json` file is what gets graded (sets are
serialized as JSON lists; the verifier converts them back before scoring).
