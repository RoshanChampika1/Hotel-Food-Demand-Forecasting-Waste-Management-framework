
"""Train the 5 food-category models and pick the winners.

Per category (rice_starch, mains, veg_sides, desserts, beverages) the target is food eaten per guest.
Five models are compared with 5-fold cross-validation (every event is predicted by a model that never
saw it). The expected-quantity winner is the model with the lowest error in kg; the safe quantity is
always the quantile GBM at P85. Winners go to models/winners.json, which src/predict.py reads.

Usage: python src/train.py [--data data/processed/master.csv]
"""
import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold

sys.path.insert(0, str(Path(__file__).parent))
from baseline_model import BaselineMeanModel  # noqa: E402
from features import build_features, FEATURE_COLUMNS  # noqa: E402

CATEGORIES = ["rice_starch", "mains", "veg_sides", "desserts", "beverages"]
QUANTILE = 0.85
RANDOM_STATE = 42
N_FOLDS = 5
MODELS_DIR = Path("models")
RESULTS_DIR = Path("results/category_models")
EXPECTED_CANDIDATES = ["baseline", "linear_regression", "random_forest", "gradient_boosting"]
SAFE_MODEL = "quantile_gbm_p85"
WASTE_COST_PER_KG = 1.0
SHORTAGE_COST_PER_KG = 3.0


def build_model_registry():
    return {
        "baseline": BaselineMeanModel(),
        "linear_regression": LinearRegression(),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=150, max_depth=3, learning_rate=0.05, random_state=RANDOM_STATE
        ),
        "quantile_gbm_p85": GradientBoostingRegressor(
            loss="quantile", alpha=QUANTILE,
            n_estimators=150, max_depth=3, learning_rate=0.05, random_state=RANDOM_STATE,
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=300, max_depth=8, min_samples_leaf=3, random_state=RANDOM_STATE
        ),
    }


def compute_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Per-category consumed-per-guest rate for every category."""
    targets = {
        cat: (df[f"prepared_{cat}"] - df[f"leftover_{cat}"]) / df["guests_actual"]
        for cat in CATEGORIES
    }
    return pd.DataFrame(targets, index=df.index)


def cross_val_predict_all(X: pd.DataFrame, y: pd.Series, n_splits=N_FOLDS, random_state=RANDOM_STATE):
    """Out-of-fold predictions for every model in the registry.

    Returns {model_name: np.array of length len(X)} — row i's value was
    predicted by a model instance that never trained on row i.
    """
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    oof = {name: np.zeros(len(X)) for name in build_model_registry()}

    for train_idx, val_idx in kf.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train = y.iloc[train_idx]
        for name, model in build_model_registry().items():
            model.fit(X_train, y_train)
            oof[name][val_idx] = model.predict(X_val)

    return oof


def mae_rate_and_qty(y_true_rate, pred_rate, guests_actual):
    mae_rate = mean_absolute_error(y_true_rate, pred_rate)
    mae_qty = mean_absolute_error(y_true_rate * guests_actual, pred_rate * guests_actual)
    return mae_rate, mae_qty


def total_cost(y_true_rate, pred_rate, guests_actual):
    """Illustrative asymmetric cost: shortage costs more per kg than waste."""
    true_qty = y_true_rate * guests_actual
    pred_qty = pred_rate * guests_actual
    surplus = np.maximum(pred_qty - true_qty, 0)
    shortage = np.maximum(true_qty - pred_qty, 0)
    return float((surplus * WASTE_COST_PER_KG + shortage * SHORTAGE_COST_PER_KG).sum())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default="data/processed/master.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.data)
    before = len(df)
    df = df[df["guests_actual"] > 0].reset_index(drop=True)
    if len(df) < before:
        print(f"Dropped {before - len(df)} row(s) with guests_actual <= 0.\n")

    X_all = build_features(df)
    y_all = compute_targets(df)
    guests_all = df["guests_actual"].to_numpy()

    MODELS_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Training on {len(df)} events from {args.data}")
    print(f"{N_FOLDS}-fold cross-validation (each row's prediction is from a model that never trained on it)\n")
    print(f"{'category':<12} {'model':<18} {'n':>4} {'MAE/guest':>10} {'MAE(kg)':>9} {'RMSE(kg)':>9} {'R2':>6} {'cost':>9}")
    print("-" * 84)

    rows, oof_rows, winners = [], [], {}
    for cat in CATEGORIES:
        mask = y_all[cat].notna().to_numpy()
        X, y, guests = X_all[mask].reset_index(drop=True), y_all[cat][mask].reset_index(drop=True), guests_all[mask]
        oof = cross_val_predict_all(X, y)
        yt = y.to_numpy()
        for name, pred in oof.items():
            mae_rate, mae_qty = mae_rate_and_qty(yt, pred, guests)
            rows.append({
                "category": cat, "model": name, "n_events": int(mask.sum()),
                "mae_per_guest": mae_rate, "mae_kg": mae_qty,
                "rmse_kg": float(np.sqrt(mean_squared_error(yt * guests, pred * guests))),
                "r2": r2_score(yt, pred), "cost": total_cost(yt, pred, guests),
                "coverage": float((yt <= pred).mean()),
            })
            r = rows[-1]
            print(f"{cat:<12} {name:<18} {r['n_events']:>4} {mae_rate:>10.4f} {mae_qty:>9.3f} "
                  f"{r['rmse_kg']:>9.3f} {r['r2']:>6.3f} {r['cost']:>9.1f}")
        cat_rows = [r for r in rows if r["category"] == cat]
        expected = min((r for r in cat_rows if r["model"] in EXPECTED_CANDIDATES), key=lambda r: r["mae_kg"])["model"]
        winners[cat] = {"expected": expected, "safe": SAFE_MODEL}
        print(f"  -> winner for {cat}: expected = {expected}, safe = {SAFE_MODEL}\n")

        idx = df.index[mask]
        for name, pred in oof.items():
            oof_rows.append(pd.DataFrame({"event_id": df.loc[idx, "event_id"].to_numpy(), "category": cat,
                                          "model": name, "y_true": yt, "y_pred": pred, "guests_actual": guests}))

        for name, model in build_model_registry().items():
            model.fit(X, y)
            joblib.dump(model, MODELS_DIR / f"{cat}__{name}.joblib")

    comparison = pd.DataFrame(rows)
    comparison.to_csv(RESULTS_DIR / "model_comparison.csv", index=False)
    pd.concat(oof_rows, ignore_index=True).to_csv(RESULTS_DIR / "oof_predictions.csv", index=False)
    (MODELS_DIR / "winners.json").write_text(json.dumps(winners, indent=2), encoding="utf-8")

    print("P85 calibration check (target: ~0.85, share of events where the safe amount was enough):")
    for r in comparison[comparison.model == SAFE_MODEL].itertuples():
        flag = "" if 0.75 <= r.coverage <= 0.95 else "  <-- off target"
        print(f"  {r.category:<12} coverage={r.coverage:.2f}{flag}")
    print()

    print(f"Cost comparison (shortage weighted {SHORTAGE_COST_PER_KG / WASTE_COST_PER_KG:.0f}x worse than surplus per kg):")
    for cat in CATEGORIES:
        c = comparison[comparison.category == cat].set_index("model")["cost"]
        best = c.drop("baseline").idxmin()
        saving = 100 * (c["baseline"] - c[best]) / c["baseline"] if c["baseline"] else 0.0
        print(f"  {cat:<12} baseline={c['baseline']:>8.1f}  {best}={c[best]:>8.1f}  savings={saving:>5.1f}%")
    print()

    print("Feature importance (gradient_boosting, top 5 per category):")
    for cat in CATEGORIES:
        model = joblib.load(MODELS_DIR / f"{cat}__gradient_boosting.joblib")
        importances = pd.Series(model.feature_importances_, index=FEATURE_COLUMNS).sort_values(ascending=False)
        top5 = ", ".join(f"{feat}={imp:.2f}" for feat, imp in importances.head(5).items())
        print(f"  {cat:<12} {top5}")
    print()

    oof = pd.concat(oof_rows, ignore_index=True).merge(df[["event_id", "data_quality"]], on="event_id")
    for col, value in (("data_quality", "R"),):
        sub = oof[(oof[col] == value) & (oof.model.isin(["baseline", "gradient_boosting"]))]
        print(f"Robustness check: {col} == '{value}' only")
        for (cat, name), g in sub.groupby(["category", "model"], sort=False):
            if len(g) >= 10:
                print(f"  {cat:<12} {name:<18} n={len(g):>3}  MAE(kg)="
                      f"{mean_absolute_error(g.y_true * g.guests_actual, g.y_pred * g.guests_actual):.3f}")
        print()

    print(f"Winners written to {MODELS_DIR / 'winners.json'}; comparison in {RESULTS_DIR / 'model_comparison.csv'}")


if __name__ == "__main__":
    main()
