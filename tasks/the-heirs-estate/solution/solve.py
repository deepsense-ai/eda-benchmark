"""Reference solver for the heir's estate task."""
import os

import pandas as pd

# Human observation from genealogy_trees.txt:
# Dawid Majtyka -> great-great-grandparent Przemysław Kurczab.
# Among Przemysław Kurczab's direct children, only those with
# strictly more than one grandchild count:
# - Liwia Maligłówka (grandchildren visible under their descendants)
# - Alan Wocial
# Julianna Paściak and Julita Kucharz are excluded on the grandchildren rule.
TARGET_HEIRS = {
    ("Liwia", "Maligłówka"),
    ("Alan", "Wocial"),
}


def solve(data_folder: str) -> int:
    """Read balances for manually identified heirs and return their sum."""
    accounts_path = os.path.join(data_folder, "people_accounts.csv")
    df = pd.read_csv(accounts_path)
    heirs = pd.DataFrame(
        list(TARGET_HEIRS), columns=["first_name", "last_name"]
    )
    merged = df.merge(heirs, on=["first_name", "last_name"], how="inner")
    return int(merged["account_balance"].sum())


ANSWER_PY_TEMPLATE = '''def answer() -> int:
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
    print(f"solved: {result}")
