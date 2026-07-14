# The Heir's Estate

****Task:****
Find the great-great-grandparent of 'Dawid Majtyka' in the family tree. Using the database, sum the account
balances of their direct children who have more than one grandchild. Return only the final integer.

Note: Assume this family tree originates from a fictional culture where reproduction is recorded through a single
primary lineage and surnames are individually adopted. For simplicity, this family tree tracks a single lineage.
Spouses and marriage records are intentionally omitted as they are not relevant.

Due to the degradation of the original historical record, lines in the diagram appear jagged and fragmented,
but the genealogical paths remain traceable.

****Dataset:****
To access the dataset use the files:
- /app/dataset/genealogy_trees.txt
- /app/dataset/people_accounts.csv

****Validation:****
Your final answer will be evaluated with the function in this snippet:

```python
def calculate_int_score(answer: int, gt: int) -> float:
    """Calculates the score of integer values. The function works as follows:
    For gt <= 100 we have:
    - answer = gt -> score 1
    - |answer - gt| = 1 -> score 1/2
    - |answer - gt| = 2 -> score 1/3
    - ...
    For gt > 100, we compute 1% of gt and tune the score so that:
    - answer = gt -> score 1
    - |answer - gt| = 1% of gt -> score 1/2
    - |answer - gt| = 2% of gt -> score 1/3
    - ...

    Args:
        gt: The ground truth value.
        answer: The predicted value.

    Returns:
        The score as a float.
    """
    error_giving_score_half = float(max(gt / 100.0, 1))
    return 1.0 / (abs(gt - answer) / error_giving_score_half + 1.0)
```

****Answer format:****
Write your answer as a Python file at `/app/answer.py` that defines an `answer()` function
and, when executed, saves the returned value as JSON to `/app/answer.json`:

```python
def answer() -> int:
    # some logic
    return 1234

if __name__ == "__main__":
    import json
    with open("/app/answer.json", "w") as f:
        json.dump(answer(), f, default=list)
```

Before you finish, run `python /app/answer.py` so that both `/app/answer.py` and
`/app/answer.json` exist. The `/app/answer.json` file is what gets graded.
