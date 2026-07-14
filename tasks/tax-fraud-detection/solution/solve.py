"""Reference solver for the tax fraud detection task."""
from collections import defaultdict
import math
from pathlib import Path

import pandas as pd

# STATISTICAL VALUE: Dataset reference date for registration age calculations
REFERENCE_DATE = pd.Timestamp("2020-01-01")

# THRESHOLD: Target audit registry size required by task specification
TOP_K = 10


def solve(data_folder: str) -> set[int]:
    """
    @brief Solves the tax fraud detection task by identifying the
           top 10 anomalous companies.

    @param data_folder Path to the directory containing dataset files
                       (companies.csv, invoices.csv).
    @return A set of 10 company IDs most likely to require
            tax audit/investigation.
    """
    data_dir = Path(data_folder)
    companies = pd.read_csv(data_dir / "companies.csv")
    invoices = pd.read_csv(data_dir / "invoices.csv")

    company_ids_set: set[int] = set(companies["company_id"].astype(int))

    b_raw = _score_benford(invoices)
    b_scores = {}
    for cid, chi in b_raw.items():
        # STATISTICAL VALUE: Exact mean (8.0) and std (4.0) of
        # Chi-Square(df=8) distribution under the null hypothesis
        b_scores[cid] = (chi - 8.0) / 4.0

    p_scores = _score_phantom(companies, invoices)

    ch_scores = _score_charity(companies, invoices, company_ids_set)

    merged: dict[int, float] = defaultdict(float)
    for d in [b_scores, p_scores, ch_scores]:
        for cid, score in d.items():
            # THRESHOLD: Filter out non-anomalous entities (below average)
            if score > 0:
                merged[cid] += score

    scored = pd.Series(merged).sort_values(ascending=False)
    return set(scored.head(TOP_K).index.astype(int))


def _score_benford(invoices: pd.DataFrame) -> dict[int, float]:
    """
    @brief Computes the Chi-Square Goodness-of-Fit test statistic
           for first digits of invoice amounts to dynamically
           detect deviations from Benford's Law.

    @param invoices A pandas DataFrame containing transaction invoices.
    @return A dictionary mapping seller IDs to their calculated
            Chi-Square test statistic.
    """
    seller_digits = invoices[["seller_id", "net_amount"]].copy()
    seller_digits["first_digit"] = (
        seller_digits["net_amount"].astype(int).astype(str).str[0].astype(int)
    )
    seller_digits = seller_digits[seller_digits["first_digit"].between(1, 9)]

    grouped = seller_digits.groupby("seller_id")
    scores: dict[int, float] = {}

    benford_expected = {d: math.log10(1 + 1 / d) for d in range(1, 10)}

    for seller_id, group in grouped:
        n = len(group)
        # THRESHOLD: Minimum invoice sample size for Chi-Square validity
        if n < 15:
            continue

        # THRESHOLD: Filter pricing traps (fixed pricing has nunique <= 2
        # or coefficient of variation CV < 2%)
        if (
            group["net_amount"].nunique() <= 2
            or (group["net_amount"].std() / group["net_amount"].mean()) < 0.02
        ):
            continue

        observed_counts = group["first_digit"].value_counts().to_dict()

        chi_sq = 0.0
        for d in range(1, 10):
            observed = float(observed_counts.get(d, 0))
            expected = n * benford_expected[d]
            chi_sq += ((observed - expected) ** 2) / expected

        scores[int(seller_id)] = chi_sq

    return scores


def _score_phantom(
    companies: pd.DataFrame,
    invoices: pd.DataFrame,
) -> dict[int, float]:
    """
    @brief Detects shell/phantom vendors dynamically by computing multivariate
           capacity-to-purchase ratios relative to the entire population.

    @param companies A pandas DataFrame with company registration metadata.
    @param invoices A pandas DataFrame with all transactional invoices.
    @return A dictionary mapping company IDs to their phantom fraud z-scores.
    """
    incoming = invoices.groupby("buyer_id").agg(
        incoming_invoice_count=("invoice_id", "size"),
        supplier_count=("seller_id", "nunique"),
        total_vat_paid=("vat_amount", "sum"),
        total_purchases=("net_amount", "sum"),
    )
    outgoing = (
        invoices.groupby("seller_id").size().rename("outgoing_invoice_count")
    )

    comp = companies.copy()
    comp["registration_date"] = pd.to_datetime(comp["registration_date"])
    comp["company_age_days"] = (
        REFERENCE_DATE - comp["registration_date"]
    ).dt.days
    comp = comp.set_index("company_id")

    company_flow = (
        comp[
            [
                "company_age_days",
                "employees",
                "declared_revenue_annual",
                "bank_account_age_months",
            ]
        ]
        .join(incoming, how="left")
        .join(outgoing, how="left")
        .fillna(
            {
                "incoming_invoice_count": 0,
                "supplier_count": 0,
                "total_vat_paid": 0,
                "total_purchases": 0,
                "outgoing_invoice_count": 0,
            }
        )
    )

    # THRESHOLD: Structural limit for buyer-only shell company classification
    buyer_only = company_flow[company_flow["outgoing_invoice_count"] <= 1]
    if buyer_only.empty:
        return {}

    # NUMERICAL GUARD: Prevent division by zero for zero-revenue shell
    # structures
    company_flow["purchase_revenue_ratio"] = company_flow["total_purchases"] / (
        company_flow["declared_revenue_annual"].clip(lower=100.0)
    )
    # NUMERICAL GUARD: Prevent division by zero for zero-employee companies
    company_flow["vat_employee_ratio"] = company_flow["total_vat_paid"] / (
        company_flow["employees"] + 1
    )

    # STRUCTURAL VALUE: Directional alignment of suspicion
    # (-1 = younger is suspicious, 1 = higher is suspicious)
    metrics: dict[str, int] = {
        "company_age_days": -1,
        "purchase_revenue_ratio": 1,
        "vat_employee_ratio": 1,
        "bank_account_age_months": 1,
    }

    z_frame = pd.DataFrame(index=company_flow.index)
    for col, direction in metrics.items():
        values = company_flow[col].dropna()
        if len(values) < 2:
            continue
        mean_val = values.mean()
        std_val = values.std()
        if std_val == 0 or pd.isna(std_val):
            continue
        z_frame[col] = ((company_flow[col] - mean_val) / std_val) * direction

    buyer_only_z = z_frame.loc[buyer_only.index]
    if buyer_only_z.empty:
        return {}

    combined_z = buyer_only_z.mean(axis=1)

    scores: dict[int, float] = {}
    for company_id, z_val in combined_z.items():
        # THRESHOLD: Filter out non-anomalous entities (below average)
        if z_val > 0:
            scores[int(company_id)] = float(z_val)
    return scores


def _score_charity(
    companies: pd.DataFrame,
    invoices: pd.DataFrame,
    company_ids_set: set[int],
) -> dict[int, float]:
    """
    @brief Detects charity invoice laundering by dynamically identifying
           outsized transaction volumes routed to unregistered
           EIN-formatted entity IDs.

    @param companies A pandas DataFrame with company registration metadata.
    @param invoices A pandas DataFrame with all transactional invoices.
    @param company_ids_set A set of registered company IDs.
    @return A dictionary mapping donor company IDs to their charity
            laundering fraud scores.
    """
    unregistered_invoices = invoices.loc[
        ~invoices["buyer_id"].isin(company_ids_set)
    ].copy()

    if unregistered_invoices.empty:
        return {}

    unregistered_invoices["id_len"] = (
        unregistered_invoices["buyer_id"].astype(int).astype(str).str.len()
    )

    # THRESHOLD: Format length representing EIN unregistered buyer IDs
    charity_outgoing = unregistered_invoices.loc[
        unregistered_invoices["id_len"] == 8
    ].copy()

    if charity_outgoing.empty:
        return {}

    donor_stats = charity_outgoing.groupby("seller_id").agg(
        charity_invoice_count=("invoice_id", "size"),
        charity_recipient_count=("buyer_id", "nunique"),
        charity_total_net=("net_amount", "sum"),
    )

    donor_stats = donor_stats.join(
        companies.set_index("company_id")["declared_revenue_annual"],
        how="left",
    )
    # NUMERICAL GUARD: Prevent division by zero on revenue coverage gap
    donor_stats["declared_revenue_annual"] = donor_stats[
        "declared_revenue_annual"
    ].fillna(1.0)
    donor_stats["coverage_gap"] = (
        donor_stats["charity_total_net"]
        - donor_stats["declared_revenue_annual"]
    )

    # THRESHOLD: Minimum population size to compute standard z-scores
    if len(donor_stats) < 3:
        # STATISTICAL VALUE: Standard z-score fallback representation
        return {int(cid): 1.0 for cid in donor_stats.index}

    cols: list[str] = [
        "charity_invoice_count",
        "charity_total_net",
        "coverage_gap",
    ]
    z_frame = pd.DataFrame(index=donor_stats.index)
    for col in cols:
        values = donor_stats[col].dropna()
        if len(values) < 2:
            continue
        mean_val = values.mean()
        std_val = values.std()
        if std_val == 0 or pd.isna(std_val):
            continue
        z_frame[col] = (donor_stats[col] - mean_val) / std_val

    rec_values = donor_stats["charity_recipient_count"].dropna()
    if len(rec_values) >= 2:
        rec_std = rec_values.std()
        if rec_std > 0 and not pd.isna(rec_std):
            rec_mean = rec_values.mean()
            z_frame["charity_recipient_count"] = (
                donor_stats["charity_recipient_count"] - rec_mean
            ) / rec_std

    if z_frame.empty:
        # STATISTICAL VALUE: Standard z-score fallback representation
        return {int(cid): 1.0 for cid in donor_stats.index}

    combined_z = z_frame.mean(axis=1)

    scores: dict[int, float] = {}
    for company_id, z_val in combined_z.items():
        # THRESHOLD: Filter out non-anomalous entities (below average)
        if z_val > 0:
            scores[int(company_id)] = float(z_val)
    return scores


ANSWER_PY_TEMPLATE = '''def answer() -> set[int]:
    return {result!r}

if __name__ == "__main__":
    import json
    with open("/app/answer.json", "w") as f:
        json.dump(answer(), f, default=list)
'''


if __name__ == "__main__":
    result = solve("/app/dataset")
    Path("/app/answer.py").write_text(ANSWER_PY_TEMPLATE.format(result=result))
    print(f"solved: {sorted(result)}")
