"""Clean the combined event table into the training-ready master dataset.

Input : data/combined/all_events.csv   (one row per event; see docs/dataset.md)
Output: data/processed/master.csv      one clean row per event
        reports/qc_report.md           what was fixed or removed, and why

Steps
  1. Text columns: trim, lower-case, map aliases (day -> lunch, night -> dinner); unknown event
     types become "other".
  2. Types: dates and numbers parsed; rows with no date or no guest count are dropped; duplicate
     event_ids are dropped (first one kept).
  3. Quantities: negative amounts are blanked; a leftover larger than what was prepared is capped
     at the prepared amount.
  4. Outliers: per category, an eaten-per-guest value far outside the normal range (beyond 3 x IQR
     from the quartiles) is blanked for that category only. This catches partly-read workbooks
     where only a few dishes were picked up. The rest of the event is kept.
  5. data_quality (R/M/E) is kept unchanged.

Run:  python src/preprocess.py [--data data/combined/all_events.csv]
"""
import argparse
from pathlib import Path

import pandas as pd

CATEGORIES = ["rice_starch", "mains", "veg_sides", "desserts", "beverages"]
EVENT_TYPES = ["wedding", "corporate", "birthday", "other"]
MEAL_ALIASES = {"lunch": "lunch", "day": "lunch", "dinner": "dinner", "night": "dinner"}
NUMERIC = (["month", "is_weekend", "road_km", "rate_lkr", "n_dishes_total", "guests_expected", "guests_actual"]
           + [f"{k}_{c}" for c in CATEGORIES for k in ("prepared", "leftover", "ran_short")])
IQR_K = 3.0


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    issues = []
    df = df.copy()
    n0 = len(df)

    for col in ("event_type", "meal_type", "data_quality", "hotel_id"):
        df[col] = df[col].astype(str).str.strip()
    df["event_type"] = df["event_type"].str.lower()
    unknown = ~df["event_type"].isin(EVENT_TYPES)
    if unknown.any():
        issues.append(f"{int(unknown.sum())} rows: unknown event_type set to 'other'")
    df.loc[unknown, "event_type"] = "other"
    df["meal_type"] = df["meal_type"].str.lower().map(MEAL_ALIASES)
    df["data_quality"] = df["data_quality"].str.upper()

    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    for col in NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    bad = df["event_date"].isna() | ~(df["guests_expected"] > 0) | ~(df["guests_actual"] > 0) | df["meal_type"].isna()
    if bad.any():
        issues.append(f"{int(bad.sum())} rows dropped: missing date, meal type or guest count")
    df = df[~bad]
    dup = df["event_id"].duplicated()
    if dup.any():
        issues.append(f"{int(dup.sum())} rows dropped: duplicate event_id")
    df = df[~dup].copy()

    df["month"] = df["event_date"].dt.month
    df["is_weekend"] = (df["event_date"].dt.dayofweek >= 5).astype(int)

    for c in CATEGORIES:
        prep, left = f"prepared_{c}", f"leftover_{c}"
        neg = (df[prep] < 0) | (df[left] < 0)
        if neg.any():
            issues.append(f"{int(neg.sum())} rows: negative {c} amount blanked")
        df.loc[neg, [prep, left]] = pd.NA
        excess = df[left] > df[prep]
        if excess.any():
            issues.append(f"{int(excess.sum())} rows: leftover_{c} > prepared_{c}, capped at prepared")
        df.loc[excess, left] = df.loc[excess, prep]

        rate = (df[prep] - df[left]) / df["guests_actual"]
        q1, q3 = rate.quantile([0.25, 0.75])
        lo, hi = q1 - IQR_K * (q3 - q1), q3 + IQR_K * (q3 - q1)
        out = rate.notna() & ((rate < lo) | (rate > hi))
        if out.any():
            issues.append(f"{int(out.sum())} rows: {c} eaten-per-guest outside [{lo:.3f}, {hi:.3f}] "
                          f"blanked for {c} only")
        df.loc[out, [prep, left, f"ran_short_{c}"]] = pd.NA

    df["event_date"] = df["event_date"].dt.strftime("%Y-%m-%d")
    for c in CATEGORIES:
        df[f"ran_short_{c}"] = df[f"ran_short_{c}"].astype("Int64")
    issues.insert(0, f"{len(df)} of {n0} rows kept")
    return df.reset_index(drop=True), issues


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="data/combined/all_events.csv")
    p.add_argument("--out", default="data/processed/master.csv")
    p.add_argument("--report", default="reports/qc_report.md")
    a = p.parse_args()

    df, issues = clean(pd.read_csv(a.data))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)

    usable = {c: int(df[f"prepared_{c}"].notna().sum()) for c in CATEGORIES}
    lines = ["# Data quality report", "", f"Input: `{a.data}` -> output: `{a.out}`", ""]
    lines += [f"- {i}" for i in issues]
    lines += ["", "| | count |", "|---|---|"]
    lines += [f"| hotel = {k} | {v} |" for k, v in df["hotel_id"].value_counts().sort_index().items()]
    lines += [f"| data_quality = {k} | {v} |" for k, v in df["data_quality"].value_counts().sort_index().items()]
    lines += [f"| events with a {c} target | {v} |" for c, v in usable.items()]
    Path(a.report).parent.mkdir(parents=True, exist_ok=True)
    Path(a.report).write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {a.out} ({len(df)} rows) and {a.report}")
    for i in issues:
        print(f"  - {i}")
    print("Rows by data_quality:", df["data_quality"].value_counts().to_dict())
    print("Events with a target per category:", usable)


if __name__ == "__main__":
    main()
