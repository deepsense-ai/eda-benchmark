# Cleaning Service

****Task:****
Using the three provided files (tasks.csv, employees.csv, and timesheet.csv),
calculate the total monthly salary for each employee for every month. The total salary is the sum of:
(total hours worked in the month × hourly rate) + any bonuses earned for completed tasks in that month.
Final salary values should be rounded to the nearest integer using standard mathematical rounding.
For each month, the billing period for all employees starts on the same day of the week inherited from the
dataset's earliest record.
On that day, employees are required to appear at the workplace to collect their salary.
If any invalid or inconsistent data are found in the input,
they should be corrected where possible based on available data, or otherwise excluded from the final results.
Provide the answer by generating a function that will return the total monthly salaries as:
a dictionary mapping PESEL → list of integer salaries.
For each PESEL, the list of salaries should be sorted by billing month in ascending order.

****Dataset:****
To access the dataset use the files:
- /app/dataset/employees.csv
- /app/dataset/tasks.csv
- /app/dataset/timesheet.csv

****Validation:****
Your final answer will be evaluated with the function in this snippet:

```python
def calculate_dict_of_lists_score(answer: dict[str, list],
                                  gt: dict[str, list]) -> float:
    return calculate_dict_score(answer, gt,
                                calculate_jaccard_index_with_order_factor)


def calculate_dict_score(
    answer: dict,
    gt: dict,
    score_func: Callable[[Any, Any], float],
) -> float:
    total_score = 0.0
    for gt_key, gt_value in gt.items():
        if gt_key in answer:
            answer_value = answer[gt_key]
            total_score += score_func(answer_value, gt_value)
    max_len = max(len(answer), len(gt))
    return total_score / max_len if max_len > 0 else 0.0


def calculate_jaccard_index_with_order_factor(answer_list: list,
                                              gt_list: list) -> float:
    """Calculates the Jaccard index with order factor given two lists:
     ground truth and answer list.

    The order factor is computed as follows:
    - Iterate over the answer list, denote the i-th element as item(i).
    - For item(i), add w(i) * distance_factor(i) to the resulting numerator
     and add w(i) to the resulting denominator.
    - w(i) = 0.9 ** i.
    - Denote max(len(gt_list), len(answer_list)) as max_len.
    - distance_factor(i) = 1 - distance(i) / max_len if item(i) is in the
     gt list, 0 elsewhere.
    - distance(i) = |i - position of item(i) in the gt list|.
    - After an item in the answer list is matched with its counterpart
      in the ground-truth list,
      replace both positions with placeholders to prevent future items
      from matching against already-paired entries.

    Args:
        gt_list: A list representing the ground truth values.
        answer_list: A list representing the predicted values.

    Returns:
        The Jaccard index with order factor as a float.
    """
    jaccard_index = calculate_jaccard_index(answer_list, gt_list)

    max_len = max(len(gt_list), len(answer_list))
    numerator = 0.0
    denominator = 0.0
    # We replace matching pairs with placeholders to deal with the case
    # of repeated list elements.
    placeholder = "<PLACEHOLDER>"
    gt_copy = gt_list.copy()
    for i, item in enumerate(answer_list):
        weight = 0.9**i
        if item in gt_copy:
            gt_i = gt_copy.index(item)
            distance = abs(i - gt_i)
            gt_copy[gt_i] = placeholder
        else:
            distance = max_len
        numerator += weight * (1 - distance / max_len)
        denominator += weight
    order_factor = numerator / denominator if denominator > 0 else 1.0

    return jaccard_index * order_factor


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
def answer() -> dict[str, list[int]]:
    # logic to compute total salaries per month
    return {
        "11111111111": [1111, 2222, 3333, 4444],
        "22222222222": [5555, 6666, 7777, 8888]
    }

if __name__ == "__main__":
    import json
    with open("/app/answer.json", "w") as f:
        json.dump(answer(), f, default=list)
```

Before you finish, run `python /app/answer.py` so that both `/app/answer.py` and
`/app/answer.json` exist. The `/app/answer.json` file is what gets graded.
