
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from features import build_features  # noqa: E402

CATEGORIES = ["rice_starch", "mains", "veg_sides", "desserts", "beverages"]
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


EXPECTED_MODEL_NAME = "gradient_boosting"
SAFE_MODEL_NAME = "quantile_gbm_p85"

_model_cache = {}


def _load_model(category: str, model_name: str):
   
    key = (category, model_name)
    if key not in _model_cache:
        path = MODELS_DIR / f"{category}__{model_name}.joblib"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found — run `python src/train.py` before predicting.")
        _model_cache[key] = joblib.load(path)
    return _model_cache[key]


def predict_event(event: dict) -> dict:

    X = build_features(pd.DataFrame([event]))
    guests_expected = float(event["guests_expected"])

    results = {}
    for cat in CATEGORIES:
        expected_rate = _load_model(cat, EXPECTED_MODEL_NAME).predict(X)[0]
        safe_rate = _load_model(cat, SAFE_MODEL_NAME).predict(X)[0]

        expected_qty = max(expected_rate, 0.0) * guests_expected
        safe_qty = max(safe_rate, 0.0) * guests_expected


        safe_qty = max(safe_qty, expected_qty)

        results[cat] = {"expected": round(expected_qty, 2), "safe": round(safe_qty, 2)}
    return results


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
