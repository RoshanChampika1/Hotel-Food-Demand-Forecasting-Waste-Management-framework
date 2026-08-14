
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from features import EVENT_TYPES, MEAL_TYPES  # noqa: E402

CATEGORIES = ["rice_starch", "mains", "veg_sides", "desserts", "beverages"]
DATA_QUALITY_VALUES = {"R", "M", "E"}
YES_NO_VALUES = {"Yes", "No"}

REQUIRED_COLUMNS = (
    ["hotel_id", "event_id", "event_date", "event_type", "meal_type", "guests_expected", "guests_actual"]
    + [f"{prefix}_{cat}" for cat in CATEGORIES for prefix in ("prepared", "leftover", "ran_short")]
    + ["data_quality", "notes"]
)


def load(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path, sheet_name="Event Data")
    return pd.read_csv(path)


def is_positive_number(val) -> bool:
    return pd.api.types.is_number(val) and not isinstance(val, bool) and val > 0


def is_nonnegative_number(val) -> bool:
    return pd.api.types.is_number(val) and not isinstance(val, bool) and val >= 0


def validate(df: pd.DataFrame):
 
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        return [(None, f"missing column(s): {missing_cols} — is this the right template?")]

    issues = []
    seen_event_ids = set()

    for pos, row in df.iterrows():
        excel_row = pos + 2 

        if row.isna().all():
            continue  

        notes = str(row.get("notes", "") or "")
        if "sample row" in notes.lower():
            issues.append((excel_row, "this looks like the unedited sample row — delete it before submitting"))
            continue

        event_id = row.get("event_id")
        if pd.isna(event_id) or str(event_id).strip() == "":
            issues.append((excel_row, "missing event_id"))
        elif event_id in seen_event_ids:
            issues.append((excel_row, f"duplicate event_id '{event_id}'"))
        else:
            seen_event_ids.add(event_id)

        if pd.isna(row.get("event_date")):
            issues.append((excel_row, "missing event_date"))
        else:
            try:
                pd.to_datetime(row["event_date"])
            except (ValueError, TypeError):
                issues.append((excel_row, f"event_date '{row['event_date']}' isn't a recognizable date"))

        event_type = row.get("event_type")
        if pd.isna(event_type) or str(event_type) not in EVENT_TYPES:
            issues.append((excel_row, f"event_type '{event_type}' not one of {EVENT_TYPES}"))

        meal_type = row.get("meal_type")
        if pd.isna(meal_type) or str(meal_type) not in MEAL_TYPES:
            issues.append((excel_row, f"meal_type '{meal_type}' not one of {MEAL_TYPES}"))

        for col in ("guests_expected", "guests_actual"):
            val = row.get(col)
            if pd.isna(val):
                issues.append((excel_row, f"missing {col}"))
            elif not is_positive_number(val):
                issues.append((excel_row, f"{col} '{val}' should be a positive number"))

        for cat in CATEGORIES:
            prepared = row.get(f"prepared_{cat}")
            leftover = row.get(f"leftover_{cat}")
            ran_short = row.get(f"ran_short_{cat}")

            for label, val in ((f"prepared_{cat}", prepared), (f"leftover_{cat}", leftover)):
                if pd.isna(val):
                    issues.append((excel_row, f"missing {label}"))
                elif not is_nonnegative_number(val):
                    issues.append((excel_row, f"{label} '{val}' should be a non-negative number"))

            if pd.api.types.is_number(prepared) and pd.api.types.is_number(leftover) and leftover > prepared:
                issues.append((excel_row, f"leftover_{cat} ({leftover}) is more than prepared_{cat} ({prepared})"))

            if pd.isna(ran_short) or str(ran_short) not in YES_NO_VALUES:
                issues.append((excel_row, f"ran_short_{cat} '{ran_short}' should be Yes or No"))

        data_quality = row.get("data_quality")
        if pd.isna(data_quality) or str(data_quality) not in DATA_QUALITY_VALUES:
            issues.append((excel_row, f"data_quality '{data_quality}' should be one of R, M, E"))

    return issues


def main():
    if len(sys.argv) != 2:
        print("Usage: python src/validate_submission.py path/to/hotel_file.xlsx")
        sys.exit(1)

    path = Path(sys.argv[1])
    df = load(path)
    issues = validate(df)

    checked = len(df.dropna(how="all"))
    print(f"Checked {checked} row(s) in {path.name}\n")

    if not issues:
        print("No issues found.")
        return

    print(f"{len(issues)} issue(s) found:")
    for row, message in issues:
        row_label = f"row {row}" if row is not None else "file"
        print(f"  [{row_label}] {message}")
    sys.exit(1)


if __name__ == "__main__":
    main()
