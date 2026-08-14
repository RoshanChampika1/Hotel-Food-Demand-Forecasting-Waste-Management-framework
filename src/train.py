
import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import KFold

sys.path.insert(0, str(Path(__file__).parent))
from features import build_features, FEATURE_COLUMNS  

CATEGORIES = ["rice_starch", "mains", "veg_sides", "desserts", "beverages"]
QUANTILE = 0.85
RANDOM_STATE = 42
N_FOLDS = 5
MODELS_DIR = Path("models")
WASTE_COST_PER_KG = 1.0
SHORTAGE_COST_PER_KG = 3.0


class BaselineMeanModel:
    """Chef's-rule baseline: the mean per-guest rate from training, ignoring all features."""

    def fit(self, X, y):
        self.mean_ = float(np.mean(y))
        return self

    def predict(self, X):
        return np.full(len(X), self.mean_)


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/dummy_dataset.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.data)
    if Path(args.data).name == "dummy_dataset.csv":
        print("NOTE: training on SYNTHETIC data — metrics below are pipeline")
        print("sanity checks only, not research results.\n")

    before = len(df)
    df = df[df["guests_actual"] > 0].reset_index(drop=True)
    if len(df) < before:
        print(f"Dropped {before - len(df)} row(s) with guests_actual <= 0.\n")

    X = build_features(df)
    y_all = compute_targets(df)
    guests_actual = df["guests_actual"].to_numpy()

    MODELS_DIR.mkdir(exist_ok=True)

    print(f"{N_FOLDS}-fold cross-validation (each row's prediction is from a model that never trained on it)\n")
    print(f"{'category':<12} {'model':<18} {'MAE/guest':>10} {'MAE(qty)':>10} {'cost':>10}")
    print("-" * 64)

    oof_by_cat = {}
    coverage_report = {}
    cost_report = {cat: {} for cat in CATEGORIES}

    for cat in CATEGORIES:
        y = y_all[cat]
        oof = cross_val_predict_all(X, y)
        oof_by_cat[cat] = oof

        for name, pred in oof.items():
            mae_rate, mae_qty = mae_rate_and_qty(y.to_numpy(), pred, guests_actual)
            c = total_cost(y.to_numpy(), pred, guests_actual)
            cost_report[cat][name] = c
            print(f"{cat:<12} {name:<18} {mae_rate:>10.4f} {mae_qty:>10.3f} {c:>10.1f}")

        best_name = min((n for n in oof if n != "baseline"), key=lambda n: cost_report[cat][n])
        print(f"  -> lowest-cost non-baseline model for {cat}: {best_name}\n")

        coverage_report[cat] = float((y.to_numpy() <= oof["quantile_gbm_p85"]).mean())

      
        for name, model in build_model_registry().items():
            model.fit(X, y)
            joblib.dump(model, MODELS_DIR / f"{cat}__{name}.joblib")

    print("P85 calibration check (target: ~0.85 — fraction of actual outcomes at or below the safe prediction):")
    for cat, coverage in coverage_report.items():
        flag = "" if 0.75 <= coverage <= 0.95 else "  <-- off target"
        print(f"  {cat:<12} coverage={coverage:.2f}{flag}")
    print()

    print(
        "Illustrative cost comparison (arbitrary units; shortage weighted "
        f"{SHORTAGE_COST_PER_KG / WASTE_COST_PER_KG:.0f}x worse than surplus per kg — "
        "NOT real hotel figures, replace once real costs are known):"
    )
    for cat in CATEGORIES:
        baseline_cost = cost_report[cat]["baseline"]
        best_name = min((n for n in cost_report[cat] if n != "baseline"), key=lambda n: cost_report[cat][n])
        best_cost = cost_report[cat][best_name]
        savings_pct = 100 * (baseline_cost - best_cost) / baseline_cost if baseline_cost else 0.0
        print(f"  {cat:<12} baseline={baseline_cost:>8.1f}  {best_name}={best_cost:>8.1f}  savings={savings_pct:>5.1f}%")
    print()

    print("Feature importance (gradient_boosting, top 5 per category):")
    for cat in CATEGORIES:
        model = joblib.load(MODELS_DIR / f"{cat}__gradient_boosting.joblib")
        importances = pd.Series(model.feature_importances_, index=FEATURE_COLUMNS).sort_values(ascending=False)
        top5 = ", ".join(f"{feat}={imp:.2f}" for feat, imp in importances.head(5).items())
        print(f"  {cat:<12} {top5}")
    print()

    if "data_quality" in df.columns:
        r_mask = (df["data_quality"] == "R").to_numpy()
        print(f"Records-only robustness check (data_quality == 'R', n={int(r_mask.sum())} of {len(df)} rows):")
        if r_mask.sum() >= 10:
            for cat in CATEGORIES:
                y = y_all[cat].to_numpy()
                pred = oof_by_cat[cat]["gradient_boosting"]
                mae_rate, mae_qty = mae_rate_and_qty(y[r_mask], pred[r_mask], guests_actual[r_mask])
                print(f"  {cat:<12} MAE/guest={mae_rate:.4f}  MAE(qty)={mae_qty:.3f}")
        else:
            print("  skipped: fewer than 10 'R' rows.")


if __name__ == "__main__":
    main()
