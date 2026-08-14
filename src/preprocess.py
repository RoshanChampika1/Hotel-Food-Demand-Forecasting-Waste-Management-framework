"""
Merge raw hotel CSVs (data/raw/*.csv) into one clean master dataset.

Each raw CSV must follow the collection template columns. This script:
  1. Concatenates all hotel files
  2. Standardizes text categories (strips whitespace, fixes casing)
  3. Validates values and drops/flags impossible rows
  4. Writes data/processed/master.csv

Run:  python src/preprocess.py
"""
from pathlib import Path
import pandas as pd

RAW_DIR = Path("data/raw")
OUT_PATH = Path("data/processed/master.csv")

VALID_EVENT_TYPES = ["Wedding", "Homecoming", "Birthday", "Corporate",
                     "Conference", "Religious/Almsgiving", "Other"]
VALID_STYLES = ["Buffet", "Plated"]
VALID_PACKAGES = ["Standard", "Silver", "Gold", "Custom"]

QTY_COLS = ["rice_starch_prepared_kg", "rice_starch_leftover_kg",
            "mains_prepared_kg", "mains_leftover_kg",
            "veg_sides_prepared_kg", "veg_sides_leftover_kg",
            "desserts_prepared_kg", "desserts_leftover_kg",
            "beverages_prepared_l", "beverages_leftover_l"]


def clean_category(series: pd.Series, valid: list[str]) -> pd.Series:
    """Trim whitespace, title-case, and map anything unrecognized to 'Other'."""
    s = series.astype(str).str.strip()
    lookup = {v.lower(): v for v in valid}
    return s.str.lower().map(lookup).fillna("Other" if "Other" in valid else valid[0])


def main() -> None:
    files = sorted(RAW_DIR.glob("*.csv"))
    if not files:
        raise SystemExit(f"No CSV files found in {RAW_DIR}/ - export the template sheets there first.")

    frames = [pd.read_csv(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    n0 = len(df)
    print(f"Loaded {n0} rows from {len(files)} file(s): {[f.name for f in files]}")

    # --- Standardize categories ---
    df["event_type"] = clean_category(df["event_type"], VALID_EVENT_TYPES)
    df["service_style"] = clean_category(df["service_style"], VALID_STYLES)
    df["package_tier"] = clean_category(df["package_tier"], VALID_PACKAGES)

    # --- Types & validation ---
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    for col in ["guests_booked", "guests_actual"] + QTY_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    issues = []
    mask_ok = pd.Series(True, index=df.index)

    bad_date = df["event_date"].isna()
    bad_guests = (df["guests_booked"] <= 0) | df["guests_booked"].isna()
    mask_ok &= ~(bad_date | bad_guests)
    if bad_date.any():
        issues.append(f"{bad_date.sum()} rows dropped: unparseable event_date")
    if bad_guests.any():
        issues.append(f"{bad_guests.sum()} rows dropped: missing/invalid guests_booked")

    # guests_actual missing -> assume booked (flag data_quality down to M)
    missing_actual = df["guests_actual"].isna() & mask_ok
    df.loc[missing_actual, "guests_actual"] = df.loc[missing_actual, "guests_booked"]
    df.loc[missing_actual, "data_quality"] = "M"
    if missing_actual.any():
        issues.append(f"{missing_actual.sum()} rows: guests_actual missing, assumed = booked (flagged M)")

    # Leftover cannot exceed prepared; negative quantities invalid
    for prep, left in zip(QTY_COLS[0::2], QTY_COLS[1::2]):
        neg = (df[prep] < 0) | (df[left] < 0)
        df.loc[neg, [prep, left]] = pd.NA
        excess = df[left] > df[prep]
        df.loc[excess, left] = df.loc[excess, prep]
        if excess.any():
            issues.append(f"{excess.sum()} rows: {left} > {prep}, capped at prepared")

    df = df[mask_ok].reset_index(drop=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    print(f"\nWrote {OUT_PATH} ({len(df)}/{n0} rows kept)")
    if issues:
        print("Data quality report:")
        for i in issues:
            print(f"  - {i}")
    print("\nRows by hotel:", df["hotel_id"].value_counts().to_dict())
    print("Rows by data_quality:", df["data_quality"].value_counts().to_dict())


if __name__ == "__main__":
    main()
