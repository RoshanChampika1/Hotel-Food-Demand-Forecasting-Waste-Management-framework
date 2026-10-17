"""Features, predictions and the app pages.

The prediction and app tests need trained models (python src/train.py ...); they are skipped, not
failed, on a fresh copy of the repo without them.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from features import FEATURE_COLUMNS, build_features
from predict import CATEGORIES, MODELS_DIR, predict_batch, predict_event

ROOT = Path(__file__).resolve().parents[1]
needs_models = pytest.mark.skipif(not (MODELS_DIR / "mains__linear_regression.joblib").exists(),
                                  reason="no trained models: run python src/train.py first")
EVENT = {"event_date": "2026-12-20", "event_type": "wedding", "meal_type": "dinner", "guests_expected": 200}


def test_features_have_a_fixed_order_and_only_booking_time_columns():
    X = build_features(pd.DataFrame([EVENT]))
    assert list(X.columns) == FEATURE_COLUMNS
    assert not any("actual" in c or "leftover" in c for c in X.columns)   # no post-event leakage


def test_unknown_category_does_not_crash_features():
    X = build_features(pd.DataFrame([{**EVENT, "event_type": "concert"}]))
    assert X.filter(like="event_type_").sum(axis=1).iloc[0] == 0


@needs_models
def test_single_event_forecast_is_positive_and_safe_is_at_least_expected():
    out = predict_event(EVENT)
    assert set(out) == set(CATEGORIES)
    for q in out.values():
        assert 0 < q["expected"] <= q["safe"]


@needs_models
def test_forecast_scales_with_guests():
    small, big = predict_event({**EVENT, "guests_expected": 100}), predict_event({**EVENT, "guests_expected": 400})
    assert big["mains"]["safe"] > small["mains"]["safe"]


@needs_models
def test_batch_matches_single_and_never_goes_below_expected():
    rng = np.random.default_rng(0)
    events = pd.DataFrame({
        "event_date": pd.date_range("2026-01-01", periods=300, freq="D").strftime("%Y-%m-%d"),
        "event_type": rng.choice(["wedding", "corporate", "birthday", "other"], 300),
        "meal_type": rng.choice(["lunch", "dinner"], 300),
        "guests_expected": rng.integers(1, 5000, 300),
    })
    pred = predict_batch(events)
    for c in CATEGORIES:
        assert (pred[f"{c}_safe"] >= pred[f"{c}_expected"]).all()
        assert (pred[f"{c}_expected"] >= 0).all()
    one = predict_event(events.iloc[0].to_dict())
    assert one["rice_starch"]["safe"] == pred["rice_starch_safe"].iloc[0]


@needs_models
def test_food_forecast_page_runs_a_forecast():
    at = AppTest.from_file(str(ROOT / "app" / "views" / "food_forecast.py"), default_timeout=60).run()
    assert not at.exception
    at.number_input[0].set_value(300)
    at.button[0].click().run()        # the form's Forecast button
    assert not at.exception
    assert "300" in " ".join(c.value for c in at.caption)


@needs_models
def test_analysis_tab_builds_totals_charts_and_excel_after_an_upload():
    from upload_validation import read_upload, validate_upload
    csv = ("event_id,event_date,event_type,meal_type,guests_expected\n"
           "A1,2026-11-14,wedding,lunch,250\nA2,2026-12-05,corporate,dinner,120\nA3,bad,wedding,lunch,90\n")
    result = validate_upload(read_upload("e.csv", csv.encode()))
    at = AppTest.from_file(str(ROOT / "app" / "views" / "food_forecast.py"), default_timeout=60)
    at.session_state["fc_batch"] = (result.valid, predict_batch(result.valid), result.errors, "e.csv")
    at.run()
    assert not at.exception
    assert any("Events" in m.value for m in at.markdown if "kpi" in m.value)


@pytest.mark.skipif(not (ROOT / "data" / "master" / "recipes.csv").exists(), reason="no hotel master data")
def test_event_order_page_loads():
    at = AppTest.from_file(str(ROOT / "app" / "views" / "event_order.py"), default_timeout=120).run()
    assert not at.exception
