"""Synthetic banquet event data generator — development only.
"""
import argparse

import numpy as np
import pandas as pd

CATEGORIES = ["rice_starch", "mains", "veg_sides", "desserts", "beverages"]


BASE_PER_GUEST = {
    "rice_starch": 0.25,
    "mains": 0.30,
    "veg_sides": 0.15,
    "desserts": 0.10,
    "beverages": 0.30,
}

EVENT_TYPES = ["wedding", "corporate", "birthday", "conference", "other"]
MEAL_TYPES = ["breakfast", "lunch", "dinner", "high_tea"]


EVENT_TYPE_MODIFIER = {
    "wedding": 1.20,
    "corporate": 0.90,
    "birthday": 1.05,
    "conference": 0.85,
    "other": 1.00,
}
MEAL_TYPE_MODIFIER = {
    "breakfast": {"rice_starch": 0.6, "mains": 0.7, "veg_sides": 0.5, "desserts": 0.4, "beverages": 1.3},
    "lunch": {"rice_starch": 1.1, "mains": 1.1, "veg_sides": 1.1, "desserts": 1.0, "beverages": 0.9},
    "dinner": {"rice_starch": 1.2, "mains": 1.3, "veg_sides": 1.1, "desserts": 1.2, "beverages": 1.0},
    "high_tea": {"rice_starch": 0.3, "mains": 0.4, "veg_sides": 0.4, "desserts": 1.4, "beverages": 1.4},
}

DATA_QUALITY_LEVELS = ["R", "M", "E"] 
DATA_QUALITY_WEIGHTS = [0.60, 0.25, 0.15]

DATA_QUALITY_NOISE = {"R": 0.03, "M": 0.10, "E": 0.20}


def _season(month):
    if month in (12, 1, 2):
        return "winter_peak" 
    if month in (6, 7, 8):
        return "mid_year"
    return "shoulder"


def generate(n_events: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []

    for i in range(n_events):
        event_type = rng.choice(EVENT_TYPES)
        meal_type = rng.choice(MEAL_TYPES)

        event_date = pd.Timestamp("2025-01-01") + pd.Timedelta(days=int(rng.integers(0, 365)))
        day_of_week = event_date.day_name()
        is_weekend = event_date.dayofweek >= 5
        month = event_date.month

        guests_expected = int(np.clip(rng.normal(150, 60), 20, 500))
      
        guests_actual = int(np.clip(guests_expected * rng.normal(1.0, 0.08), 10, 600))

        data_quality = rng.choice(DATA_QUALITY_LEVELS, p=DATA_QUALITY_WEIGHTS)
        noise_scale = DATA_QUALITY_NOISE[data_quality]

        row = {
            "event_id": f"EVT{i:04d}",
            "hotel_id": "dummy_hotel",
            "event_date": event_date.date().isoformat(),
            "event_type": event_type,
            "meal_type": meal_type,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "month": month,
            "season": _season(month),
            "guests_expected": guests_expected,
            "guests_actual": guests_actual,
            "data_quality": data_quality,
        }

        for cat in CATEGORIES:
            planned_rate = BASE_PER_GUEST[cat] * EVENT_TYPE_MODIFIER[event_type] * MEAL_TYPE_MODIFIER[meal_type][cat]
          
            safety_buffer = 1.12
            prepared = guests_expected * planned_rate * safety_buffer * rng.normal(1.0, 0.10)
            prepared = max(prepared, 0.0)

   
            true_rate = planned_rate * rng.normal(1.0, 0.15)
            consumed = guests_actual * true_rate * rng.normal(1.0, noise_scale)
            consumed = max(consumed, 0.0)

            ran_short = consumed > prepared
            leftover = max(prepared - consumed, 0.0)

            row[f"prepared_{cat}"] = round(prepared, 2)
            row[f"leftover_{cat}"] = round(leftover, 2)
            row[f"ran_short_{cat}"] = bool(ran_short)

        rows.append(row)

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-events", type=int, default=300, help="number of synthetic events to generate")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="data/dummy_dataset.csv")
    args = parser.parse_args()

    df = generate(args.n_events, args.seed)
    df.to_csv(args.out, index=False)

    print(f"Wrote {len(df)} synthetic events to {args.out}")
    print(f"data_quality breakdown:\n{df['data_quality'].value_counts()}")
    short_counts = {cat: int(df[f"ran_short_{cat}"].sum()) for cat in CATEGORIES}
    print(f"ran_short counts per category: {short_counts}")


if __name__ == "__main__":
    main()
