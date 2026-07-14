# Store Audit

****Task:****
During July 2023 the point-of-sale (POS) system experienced a
full-month outage — no transaction receipts were recorded. The
warehouse management system and IoT sensors continued operating
without interruption.

Your task is to reconstruct the expected revenue for July 2023
using the available warehouse and sensor data.
Calculate **Expected Revenue (PLN)** — total value of goods dispatched
from the warehouse that reached customers as sales. Goods that were
disposed of due to spoilage must not be counted as revenue.

**Assumption:** Every unit dispatched from the warehouse during
July 2023 was either sold or written off due to spoilage. No other
outcomes (theft, returns, inter-store transfers) occurred.

Disposal write-offs are rare and, when they occur, leave an unmistakable trace in the data. Only exclude a dispatch
from revenue if you are certain it represents a disposal event — when in doubt, count it as a sale.

****Dataset:****
To access the dataset use the files:
- /app/dataset/product_catalog.csv
- /app/dataset/temperature_logs.csv
- /app/dataset/warehouse_dispatches.csv

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
    return 4444

if __name__ == "__main__":
    import json
    with open("/app/answer.json", "w") as f:
        json.dump(answer(), f, default=list)
```

Before you finish, run `python /app/answer.py` so that both `/app/answer.py` and
`/app/answer.json` exist. The `/app/answer.json` file is what gets graded.
