"""Reference solver for the identify unusual values task."""
import numpy as np
import pandas as pd
from scipy.stats import chi2


def solve(data_folder: str) -> list[int]:
    data = pd.read_csv(data_folder + "/synthetic_stroke_data.csv")

    glucose_unusual = np.where(
        (data["avg_glucose_level"] < 20) | (data["avg_glucose_level"] > 800)
    )[0]
    bmi_unusual = np.where((data["bmi"] < 10) | (data["bmi"] > 60))[0]

    unusual_idx = np.concatenate([glucose_unusual, bmi_unusual])
    unusual_idx = np.unique(unusual_idx)

    filtered_data = np.delete(data, unusual_idx, axis=0)
    filtered_data = pd.DataFrame(filtered_data, columns=data.columns)

    outliers_bmi = _detect_outliers(filtered_data["bmi"])
    outliers_age = _detect_outliers(filtered_data["age"])
    outliers_glucose = _detect_outliers(filtered_data["avg_glucose_level"])

    transformed_glucose = None
    final_outliers_glucose = np.array([], dtype=int)

    if outliers_glucose.size:
        tmp = filtered_data["stroke"].iloc[outliers_glucose].value_counts()
        if tmp.iloc[1] / tmp.sum() < 0.5:
            if tmp.iloc[1] / tmp.sum() > 0.2:
                transformed_glucose = np.log2(
                    filtered_data["avg_glucose_level"].astype(float)
                )
                final_outliers_glucose = []
            else:
                final_outliers_glucose = outliers_glucose
        else:
            final_outliers_glucose = []

    if transformed_glucose is not None:
        transformed_outliers_glucose = _detect_outliers(transformed_glucose)
        if transformed_outliers_glucose.size:
            tmp = (
                filtered_data["stroke"]
                .iloc[transformed_outliers_glucose]
                .value_counts()
            )
            if tmp.iloc[1] / tmp.sum() < 0.5:
                final_outliers_glucose = transformed_outliers_glucose
            else:
                final_outliers_glucose = []

    first_step_outliers = np.concatenate(
        [outliers_age, outliers_bmi, final_outliers_glucose]
    )

    ids = filtered_data.iloc[first_step_outliers]["patient_id"]
    mapping = dict(zip(data["patient_id"], data.index))
    first_step_outliers_mapped = ids.map(mapping).values

    if first_step_outliers.size > 0:
        filtered_data = np.delete(filtered_data, first_step_outliers, axis=0)
        filtered_data = pd.DataFrame(filtered_data, columns=data.columns)

    filtered_data["risk_proxy"] = (
        filtered_data["age"]
        / filtered_data["age"].max()
        * filtered_data["avg_glucose_level"]
        / filtered_data["avg_glucose_level"].max()
        * filtered_data["bmi"]
        / filtered_data["bmi"].max()
    )

    data_to_dist = filtered_data[
        ["age", "bmi", "avg_glucose_level", "risk_proxy"]
    ].dropna()
    data_to_dist = data_to_dist.apply(pd.to_numeric, errors="coerce")

    mean_vec = data_to_dist.mean().values
    cov_matrix = np.cov(data_to_dist.values, rowvar=False)

    inv_cov = np.linalg.inv(cov_matrix)
    distances = np.apply_along_axis(
        _mahalanobis, 1, data_to_dist.values, mean_vec, inv_cov
    )
    thr = np.sqrt(chi2.ppf(0.99, df=data_to_dist.shape[1]))

    mv_outliers = distances > thr
    second_step_outliers = np.where(mv_outliers)[0]

    smoking_child = np.where(
        (filtered_data["smoking_status"].isin(["smokes", "formerly smoked"]))
        & (filtered_data["age"] < 14)
    )[0]

    working_child = np.where(
        (~filtered_data["work_type"].isin(["children", "Never_worked"]))
        & (filtered_data["age"] < 14)
    )[0]

    studing_toddlers = np.where(
        (filtered_data["work_type"] == "student") & (filtered_data["age"] < 3)
    )[0]

    second_step_outliers = np.concatenate(
        [second_step_outliers, working_child, smoking_child, studing_toddlers]
    )

    ids = filtered_data.iloc[second_step_outliers]["patient_id"]
    mapping = dict(zip(data["patient_id"], data.index))
    second_step_outliers_mapped = ids.map(mapping).values

    all_idx = np.concatenate(
        [first_step_outliers_mapped, second_step_outliers_mapped]
    )

    final_outliers = np.unique(all_idx.astype(int)).tolist()
    return final_outliers


def _detect_outliers(x) -> np.ndarray:
    """
    return the integer positions of elements in `x` that lie more than
    3·IQR below Q1 or above Q3.  `x` may be a pandas Series or any
    array‑like; NaNs are ignored.
    """
    arr = np.asarray(x, dtype=float)
    q1 = np.nanpercentile(arr, 25)
    q3 = np.nanpercentile(arr, 75)
    iqr = q3 - q1
    lower_bound = q1 - 3 * iqr
    upper_bound = q3 + 3 * iqr
    return np.where((arr < lower_bound) | (arr > upper_bound))[0]


def _mahalanobis(x, mean_vec, inv_cov):
    diff = x - mean_vec
    return np.sqrt(diff.T @ inv_cov @ diff)


ANSWER_PY_TEMPLATE = '''def answer() -> list[int]:
    return {result!r}

if __name__ == "__main__":
    import json
    with open("/app/answer.json", "w") as f:
        json.dump(answer(), f, default=list)
'''


if __name__ == "__main__":
    from pathlib import Path

    result = solve("/app/dataset")
    Path("/app/answer.py").write_text(ANSWER_PY_TEMPLATE.format(result=result))
    print(f"solved: {len(result)} outliers")
