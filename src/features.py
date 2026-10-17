import pandas as pd

EVENT_TYPES = ["wedding", "corporate", "birthday", "conference", "other"]
MEAL_TYPES = ["breakfast", "lunch", "dinner", "high_tea"]
SEASONS = ["winter_peak", "mid_year", "shoulder"]

REQUIRED_RAW_COLUMNS = ["event_date", "event_type", "meal_type", "guests_expected"]


FEATURE_COLUMNS = (
    ["guests_expected", "is_weekend"]
    + [f"event_type_{v}" for v in EVENT_TYPES]
    + [f"meal_type_{v}" for v in MEAL_TYPES]
    + [f"season_{v}" for v in SEASONS]
)


def _season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter_peak"  
    if month in (6, 7, 8):
        return "mid_year"
    return "shoulder"


def build_features(df: pd.DataFrame) -> pd.DataFrame:

    missing = [c for c in REQUIRED_RAW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required booking-time column(s): {missing}")

    event_date = pd.to_datetime(df["event_date"])

    out = pd.DataFrame(index=df.index)
    out["guests_expected"] = df["guests_expected"].astype(float)
    out["is_weekend"] = (event_date.dt.dayofweek >= 5).astype(int)

    # values outside the known lists become all-zero dummies (blank them first: newer pandas refuses them)
    event_type = pd.Categorical(df["event_type"].where(df["event_type"].isin(EVENT_TYPES)), categories=EVENT_TYPES)
    meal_type = pd.Categorical(df["meal_type"].where(df["meal_type"].isin(MEAL_TYPES)), categories=MEAL_TYPES)
    season = pd.Categorical(event_date.dt.month.map(_season), categories=SEASONS)

    out = pd.concat(
        [
            out,
            pd.get_dummies(event_type, prefix="event_type", dtype=int),
            pd.get_dummies(meal_type, prefix="meal_type", dtype=int),
            pd.get_dummies(season, prefix="season", dtype=int),
        ],
        axis=1,
    )

    return out.reindex(columns=FEATURE_COLUMNS, fill_value=0)
