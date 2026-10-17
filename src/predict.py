
import json
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from features import build_features  # noqa: E402

CATEGORIES = ["rice_starch", "mains", "veg_sides", "desserts", "beverages"]
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


# Defaults if models/winners.json is missing. train.py writes the winners of its 5-fold comparison
# there: the lowest-error model per category for the expected quantity, quantile GBM P85 for safe.
EXPECTED_MODEL_NAME = "linear_regression"
SAFE_MODEL_NAME = "quantile_gbm_p85"

_model_cache = {}


def winners() -> dict:
    path = MODELS_DIR / "winners.json"
    chosen = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {c: {"expected": chosen.get(c, {}).get("expected", EXPECTED_MODEL_NAME),
                "safe": chosen.get(c, {}).get("safe", SAFE_MODEL_NAME)} for c in CATEGORIES}


def _load_model(category: str, model_name: str):
   
    key = (category, model_name)
    if key not in _model_cache:
        path = MODELS_DIR / f"{category}__{model_name}.joblib"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found — run `python src/train.py` before predicting.")
        _model_cache[key] = joblib.load(path)
    return _model_cache[key]


def predict_batch(events: pd.DataFrame) -> pd.DataFrame:
    """Expected and safe quantity per category for many events at once (one row per event)."""
    X = build_features(events)
    guests = events["guests_expected"].astype(float).to_numpy()
    out = pd.DataFrame(index=events.index)
    chosen = winners()
    for cat in CATEGORIES:
        expected = _load_model(cat, chosen[cat]["expected"]).predict(X).clip(min=0) * guests
        safe = _load_model(cat, chosen[cat]["safe"]).predict(X).clip(min=0) * guests
        # two separately trained models can cross for unusual inputs; safe must never be below expected
        out[f"{cat}_expected"] = expected.round(2)
        out[f"{cat}_safe"] = pd.Series(safe, index=events.index).combine(
            pd.Series(expected, index=events.index), max).round(2)
    return out


def predict_event(event: dict) -> dict:
    row = predict_batch(pd.DataFrame([event])).iloc[0]
    return {cat: {"expected": row[f"{cat}_expected"], "safe": row[f"{cat}_safe"]} for cat in CATEGORIES}


if __name__ == "__main__":
    sample_event = {
        "event_date": "2026-12-20",
        "event_type": "wedding",
        "meal_type": "dinner",
        "guests_expected": 200,
    }
    print(f"Sample prediction for: {sample_event}\n")
    for cat, qty in predict_event(sample_event).items():
        print(f"{cat:<12} expected={qty['expected']:>8}  safe(P85)={qty['safe']:>8}")
