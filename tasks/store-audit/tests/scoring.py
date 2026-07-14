from collections.abc import Callable, Iterable
from typing import Any


# Used for ints
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


# Used for sets
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


# Used for lists
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


def calculate_order_score(answer_list: list, gt_list: list) -> float:
    """Scores an ordered-list answer using Spearman Footrule x LIS ratio.

    Spearman footrule similarity measures how far each element is from its
    correct position:
        footrule_sim = 1 - sum(|actual_pos - expected_pos|) / floor(n^2 / 2)

    LIS ratio measures how much of the ground-truth order is preserved as a
    longest contiguous increasing run in the rank permutation:
        lis_ratio = longest_contiguous_run / n

    Final score = footrule_sim * lis_ratio.

    Returns 0.0 if the answer contains different elements than the ground truth.

    Args:
        gt_list: A list representing the ground truth order.
        answer_list: A list representing the predicted order.

    Returns:
        The order score as a float in [0, 1].
    """
    if set(answer_list) != set(gt_list) or len(answer_list) != len(gt_list):
        return 0.0
    n = len(gt_list)
    gt_rank = {item: i for i, item in enumerate(gt_list)}
    perm = [gt_rank[item] for item in answer_list]

    footrule = sum(abs(i - perm[i]) for i in range(n))
    max_footrule = n * n // 2
    footrule_sim = 1.0 - footrule / max_footrule if max_footrule > 0 else 1.0

    breaks = [i + 1 for i in range(n - 1) if perm[i] >= perm[i + 1]]
    run_lengths = [b - a for a, b in zip([0] + breaks, breaks + [n])]
    lis_ratio = max(run_lengths) / n

    return footrule_sim * lis_ratio


def calculate_dict_of_ints_score(answer: dict,
                                 gt: dict) -> float:
    return calculate_dict_score(answer, gt, calculate_int_score)


def calculate_dict_of_sets_score(answer: dict,
                                 gt: dict) -> float:
    return calculate_dict_score(answer, gt, calculate_jaccard_index)


def calculate_dict_of_lists_score(answer: dict,
                                  gt: dict) -> float:
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
