# Air Quality Audit

****Task:****
You are reviewing an air-quality monitoring network operating across Wroclaw.
The city wants to identify stations whose readings are the least trustworthy before the data is used in downstream reporting.
Using the available station metadata, pollutant measurements, and weather measurements, identify the faulty station set.

Important:
- The faulty stations exhibit different types of anomalous behavior.
- Avoid selecting multiple stations that exhibit the same pattern if other distinct anomalies are present.
- Some measurement rows are incomplete, so treat short gaps carefully and prefer methods that
  preserve local time-series structure rather than turning missingness itself into the main signal.
- One problematic station broadly follows local patterns, but not with the same rhythm as its peers.
- Another looks plausible point-by-point yet its swings are unusually muted compared with comparable local stations.
- A third appears ordinary in aggregate, but its remaining deviations line up a bit too neatly with one environmental driver.

Return only a **set** with the 3 `station_id` values. Order does not matter.

****Dataset:****
To access the dataset use the files:
- /app/dataset/stations.csv
- /app/dataset/readings.csv
- /app/dataset/weather_stations.csv
- /app/dataset/weather_readings.csv

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
    # some logic
    return {"ST001", "ST002", "ST003", ...}

if __name__ == "__main__":
    import json
    with open("/app/answer.json", "w") as f:
        json.dump(answer(), f, default=list)
```

Before you finish, run `python /app/answer.py` so that both `/app/answer.py` and
`/app/answer.json` exist. The `/app/answer.json` file is what gets graded (sets are
serialized as JSON lists; the verifier converts them back before scoring).
