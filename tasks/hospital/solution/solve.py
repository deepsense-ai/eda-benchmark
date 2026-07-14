"""Reference solver for the hospital compensation registry task."""
import csv
from datetime import date, datetime
from pathlib import Path
from typing import TypeAlias

RegistryRow: TypeAlias = dict[str, str]

REGISTRY_FILE = "hospital_compensation_registry.csv"

REQUIRED_COLUMNS = {
    "patient_id",
    "first_name",
    "second_name",
    "full_name",
    "emergency_contact_patient_id",
    "record_date",
    "compensation_reason",
    "policy_tier",
    "coverage_status",
    "documentation_status",
    "direct_payment_usd",
}

FAMILY_LOSS_REASONS = {
    "bereavement compensation",
    "life event claim",
    "family support adjustment",
}


def solve(data_folder: str) -> set[str]:
    """Return the set of three patient IDs most likely to be deceased.

    A patient is deceased iff:
      (a) their emergency_contact_patient_id points to a family-loss
          claim row, and
      (b) they have no record dated strictly after that claim's record_date.
    """
    rows = _read_registry(Path(data_folder) / REGISTRY_FILE)
    by_patient = {_clean(r["patient_id"]): r for r in rows}

    answer: set[str] = set()
    for candidate in rows:
        ec_id = _clean(candidate["emergency_contact_patient_id"])
        if not ec_id:
            continue
        contact = by_patient.get(ec_id)
        if (
            contact is None
            or _clean(contact["compensation_reason"]) not in FAMILY_LOSS_REASONS
        ):
            continue
        if _has_record_after(candidate, contact):
            continue
        answer.add(_clean(candidate["patient_id"]))

    return answer


def _read_registry(path: Path) -> list[RegistryRow]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path.name} is empty")
    missing = sorted(REQUIRED_COLUMNS - set(rows[0].keys()))
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    return rows


def _has_record_after(candidate: RegistryRow, contact: RegistryRow) -> bool:
    cand_date = _parse_optional_date(candidate["record_date"])
    if cand_date is None:
        return False
    loss_date = datetime.strptime(
        _clean(contact["record_date"]), "%Y-%m-%d"
    ).date()
    return cand_date > loss_date


def _parse_optional_date(value: str) -> date | None:
    cleaned = _clean(value)
    return (
        None if not cleaned else datetime.strptime(cleaned, "%Y-%m-%d").date()
    )


def _clean(value: object) -> str:
    return "" if value is None else str(value).strip()


ANSWER_PY_TEMPLATE = '''def answer() -> set[str]:
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
