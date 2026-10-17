"""Full evaluation of the trained food models: metrics tables, confusion matrices and curves.

Run after train.py (it reads train.py's out-of-fold predictions, so every number is for events the
model never saw).

1. Quantity models (regression): MAE, RMSE, R2 and MAPE per category and model, for all events.
   Plots: model comparison, predicted vs actual, residuals, P85 coverage,
   learning curves, feature importance.
2. High-demand detection (from the regression models): an event is "high demand" when eaten per
   guest is above the median. Each expected-quantity model's prediction is turned into the same
   yes/no call, giving a confusion matrix, accuracy, precision, recall and F1.
3. Shortage risk (classification): will a category run short? Predicted from booking-time features
   only (src/features.py) with logistic regression, random forest and gradient boosting, against a
   "never short" baseline. 5-fold stratified CV. Confusion matrices, accuracy, precision, recall, F1,
   ROC-AUC, ROC and precision-recall curves.

Usage: python src/evaluate.py [--data data/processed/master.csv] [--out results/category_models]
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (ConfusionMatrixDisplay, accuracy_score, average_precision_score, confusion_matrix,
                             f1_score, mean_absolute_error, mean_squared_error, precision_recall_curve,
                             precision_score, r2_score, recall_score, roc_auc_score, roc_curve)
from sklearn.model_selection import KFold, StratifiedKFold, learning_curve
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).parent))
from features import FEATURE_COLUMNS, build_features  # noqa: E402
from train import (CATEGORIES, MODELS_DIR, N_FOLDS, RANDOM_STATE, SAFE_MODEL,  # noqa: E402
                   build_model_registry, compute_targets)

warnings.filterwarnings("ignore")
LABEL = {"rice_starch": "Rice & starch", "mains": "Mains", "veg_sides": "Veg & sides",
         "desserts": "Desserts", "beverages": "Beverages"}
MODEL_LABEL = {"baseline": "Chef's rule", "linear_regression": "Linear regression",
               "random_forest": "Random forest", "gradient_boosting": "Gradient boosting",
               "quantile_gbm_p85": "Quantile GBM P85"}
MODEL_COLOR = {"baseline": "#1f77b4", "linear_regression": "#ff7f0e", "random_forest": "#2ca02c",
               "gradient_boosting": "#d62728", "quantile_gbm_p85": "#9467bd"}
EXPECTED_MODELS = ["baseline", "linear_regression", "random_forest", "gradient_boosting"]


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- 1. quantity models
def regression_metrics(oof: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for subset, d in (("all", oof),):
        for (cat, model), g in d.groupby(["category", "model"], sort=False):
            t, p = g.y_true * g.guests_actual, g.y_pred * g.guests_actual
            rows.append({"subset": subset, "category": cat, "model": model, "n": len(g),
                         "mae_kg": mean_absolute_error(t, p), "rmse_kg": np.sqrt(mean_squared_error(t, p)),
                         "r2": r2_score(t, p), "r2_per_guest": r2_score(g.y_true, g.y_pred), "mape_pct": 100 * float(np.mean(np.abs(t - p) / t.clip(lower=1e-6))),
                         "coverage": float((g.y_true <= g.y_pred).mean())})
    return pd.DataFrame(rows)


def plot_model_comparison(reg, out):
    d = reg[reg.subset == "all"].pivot(index="category", columns="model", values="mae_kg").reindex(CATEGORIES)
    fig, ax = plt.subplots(figsize=(9, 4))
    d[list(MODEL_LABEL)].rename(columns=MODEL_LABEL).rename(index=LABEL).plot.bar(ax=ax, width=0.8)
    ax.set_ylabel("MAE per event (kg / L)")
    ax.set_xlabel("")
    ax.set_title("Average error per event, 5-fold cross-validation")
    ax.tick_params(axis="x", rotation=0)
    ax.legend(fontsize=8, ncol=3)
    save(fig, out / "fig_model_comparison_mae.png")


def plot_pred_vs_actual(oof, winners, out):
    fig, axes = plt.subplots(1, 5, figsize=(17, 3.8))
    for ax, cat in zip(axes, CATEGORIES):
        g = oof[(oof.category == cat) & (oof.model == winners[cat]["expected"])]
        t, p = g.y_true * g.guests_actual, g.y_pred * g.guests_actual
        ax.scatter(t, p, s=10, alpha=0.6, color="#2c7fb8")
        lim = [0, max(t.max(), p.max()) * 1.05]
        ax.plot(lim, lim, "k--", lw=1)
        ax.set_xlim(lim)
        ax.set_ylim(lim)
        ax.set_title(f"{LABEL[cat]}\n({MODEL_LABEL[winners[cat]['expected']]}, R²={r2_score(t, p):.2f})", fontsize=9)
        ax.set_xlabel("Actual eaten")
    axes[0].set_ylabel("Predicted (expected)")
    save(fig, out / "fig_predicted_vs_actual.png")


def plot_residuals(oof, winners, out):
    fig, axes = plt.subplots(1, 5, figsize=(17, 3.4), sharey=True)
    for ax, cat in zip(axes, CATEGORIES):
        g = oof[(oof.category == cat) & (oof.model == winners[cat]["expected"])]
        ax.hist((g.y_pred - g.y_true) * g.guests_actual, bins=30, color="#2c7fb8", alpha=0.85)
        ax.axvline(0, color="k", lw=1)
        ax.set_title(LABEL[cat], fontsize=9)
        ax.set_xlabel("Predicted − actual")
    axes[0].set_ylabel("Events")
    save(fig, out / "fig_residuals.png")


def plot_coverage(reg, out):
    d = reg[(reg.subset == "all") & reg.model.isin(["baseline", "linear_regression", SAFE_MODEL])]
    d = d.pivot(index="category", columns="model", values="coverage").reindex(CATEGORIES)
    fig, ax = plt.subplots(figsize=(8, 3.8))
    d.rename(columns=MODEL_LABEL).rename(index=LABEL).plot.bar(ax=ax, width=0.75)
    ax.axhline(0.85, color="k", ls="--", lw=1, label="target 0.85")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Share of events with enough food")
    ax.set_xlabel("")
    ax.tick_params(axis="x", rotation=0)
    ax.legend(fontsize=8, loc="lower right")
    ax.set_title("Coverage: how often the predicted amount was enough")
    save(fig, out / "fig_p85_coverage.png")


def plot_learning_curves(X_all, Y, winners, out):
    fig, axes = plt.subplots(1, 5, figsize=(17, 3.6), sharey=False)
    rows = []
    for ax, cat in zip(axes, CATEGORIES):
        m = Y[cat].notna().to_numpy()
        X, y = X_all[m], Y[cat][m]
        for name in dict.fromkeys(["baseline", winners[cat]["expected"], "gradient_boosting"]):
            sizes, tr, va = learning_curve(build_model_registry()[name], X, y, cv=KFold(N_FOLDS, shuffle=True,
                                           random_state=RANDOM_STATE), train_sizes=np.linspace(0.1, 1.0, 8),
                                           scoring="neg_mean_absolute_error")
            ax.plot(sizes, -va.mean(1), "o-", ms=3, color=MODEL_COLOR[name], label=f"{MODEL_LABEL[name]} (validation)")
            if name != "baseline":
                ax.plot(sizes, -tr.mean(1), ":", lw=1, color=MODEL_COLOR[name], label=f"{MODEL_LABEL[name]} (training)")
            rows += [{"category": cat, "model": name, "n_train": int(s), "train_mae_per_guest": -a,
                      "val_mae_per_guest": -b} for s, a, b in zip(sizes, tr.mean(1), va.mean(1))]
        ax.set_title(LABEL[cat], fontsize=9)
        ax.set_xlabel("Training events")
        ax.legend(fontsize=6)
    axes[0].set_ylabel("MAE per guest")
    save(fig, out / "fig_learning_curves.png")
    pd.DataFrame(rows).to_csv(out / "learning_curves.csv", index=False)


def plot_feature_importance(out):
    imp = pd.DataFrame({cat: joblib.load(MODELS_DIR / f"{cat}__gradient_boosting.joblib").feature_importances_
                        for cat in CATEGORIES}, index=FEATURE_COLUMNS)
    imp = imp.loc[imp.mean(1).sort_values().index]
    fig, ax = plt.subplots(figsize=(7, 5))
    imp.rename(columns=LABEL).plot.barh(ax=ax, width=0.8)
    ax.set_xlabel("Importance (gradient boosting)")
    ax.legend(fontsize=8)
    save(fig, out / "fig_feature_importance.png")


# ---------------------------------------------------------------- 2. high-demand detection
def high_demand(oof: pd.DataFrame, out: Path) -> pd.DataFrame:
    rows = []
    fig, axes = plt.subplots(len(EXPECTED_MODELS), 5, figsize=(16, 3.1 * len(EXPECTED_MODELS)))
    for j, cat in enumerate(CATEGORIES):
        d = oof[oof.category == cat]
        cut = d[d.model == "baseline"].y_true.median()
        for i, model in enumerate(EXPECTED_MODELS):
            g = d[d.model == model]
            t, p = (g.y_true > cut).astype(int), (g.y_pred > cut).astype(int)
            rows.append(class_scores(cat, model, t, p))
            ConfusionMatrixDisplay(confusion_matrix(t, p, labels=[0, 1]), display_labels=["normal", "high"]).plot(
                ax=axes[i, j], colorbar=False, cmap="Blues")
            axes[i, j].set_title(f"{LABEL[cat]} · {MODEL_LABEL[model]}", fontsize=8)
    fig.suptitle("High-demand detection (eaten per guest above the median): actual vs predicted", fontsize=10)
    save(fig, out / "fig_confusion_high_demand.png")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 3. shortage risk
def classifiers():
    return {
        "never_short": DummyClassifier(strategy="most_frequent"),
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced",
                                                                                  max_iter=1000)),
        "random_forest": RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=5,
                                                class_weight="balanced", random_state=RANDOM_STATE),
        "gradient_boosting": GradientBoostingClassifier(n_estimators=150, max_depth=2, learning_rate=0.05,
                                                        random_state=RANDOM_STATE),
    }


CLF_LABEL = {"never_short": "Never short (baseline)", "logistic_regression": "Logistic regression",
             "random_forest": "Random forest", "gradient_boosting": "Gradient boosting"}


def class_scores(target, model, t, p, prob=None):
    r = {"target": target, "model": model, "n": len(t), "positives": int(np.sum(t)),
         "accuracy": accuracy_score(t, p), "precision": precision_score(t, p, zero_division=0),
         "recall": recall_score(t, p, zero_division=0), "f1": f1_score(t, p, zero_division=0)}
    if prob is not None:
        r["roc_auc"] = roc_auc_score(t, prob) if len(set(t)) > 1 else np.nan
        r["pr_auc"] = average_precision_score(t, prob) if len(set(t)) > 1 else np.nan
    return r


def oof_proba(model, X, y):
    skf = StratifiedKFold(N_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    prob = np.zeros(len(y))
    for tr, va in skf.split(X, y):
        w = None
        if isinstance(model, GradientBoostingClassifier):   # no class_weight option: balance with sample weights
            pos = y[tr].mean()
            w = np.where(y[tr] == 1, 0.5 / pos, 0.5 / (1 - pos))
        model.fit(X.iloc[tr], y[tr], **({"sample_weight": w} if w is not None else {}))
        prob[va] = model.predict_proba(X.iloc[va])[:, 1]
    return prob


def shortage(df: pd.DataFrame, X_all: pd.DataFrame, out: Path) -> pd.DataFrame:
    short = df[[f"ran_short_{c}" for c in CATEGORIES]]
    targets = {"any": short.max(axis=1, skipna=True)} | {c: df[f"ran_short_{c}"] for c in CATEGORIES}
    rows, probs = [], {}
    for target, y in targets.items():
        m = y.notna().to_numpy()
        X, yy = X_all[m].reset_index(drop=True), y[m].astype(int).to_numpy()
        for name, model in classifiers().items():
            prob = oof_proba(model, X, yy)
            pred = (prob >= 0.5).astype(int)
            rows.append({"subset": "all", **class_scores(target, name, yy, pred, prob)})
            probs[(target, name)] = (yy, prob, pred)

    fig, axes = plt.subplots(1, 4, figsize=(15, 3.6))
    for ax, name in zip(axes, classifiers()):
        yy, _, pred = probs[("any", name)]
        ConfusionMatrixDisplay(confusion_matrix(yy, pred, labels=[0, 1]),
                               display_labels=["enough", "ran short"]).plot(ax=ax, colorbar=False, cmap="Oranges")
        ax.set_title(CLF_LABEL[name], fontsize=9)
    fig.suptitle("Shortage risk (any category ran short): actual vs predicted, 5-fold CV", fontsize=10)
    save(fig, out / "fig_confusion_shortage.png")

    fig, axes = plt.subplots(len(CATEGORIES), 4, figsize=(14, 3.0 * len(CATEGORIES)))
    for i, cat in enumerate(CATEGORIES):
        for j, name in enumerate(classifiers()):
            yy, _, pred = probs[(cat, name)]
            ConfusionMatrixDisplay(confusion_matrix(yy, pred, labels=[0, 1]),
                                   display_labels=["enough", "short"]).plot(ax=axes[i, j], colorbar=False,
                                                                            cmap="Oranges")
            axes[i, j].set_title(f"{LABEL[cat]} · {CLF_LABEL[name]}", fontsize=8)
    save(fig, out / "fig_confusion_shortage_by_category.png")

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.4))
    for name in classifiers():
        yy, prob, _ = probs[("any", name)]
        fpr, tpr, _ = roc_curve(yy, prob)
        a1.plot(fpr, tpr, label=f"{CLF_LABEL[name]} (AUC {roc_auc_score(yy, prob):.2f})")
        prec, rec, _ = precision_recall_curve(yy, prob)
        a2.plot(rec, prec, label=f"{CLF_LABEL[name]} (AP {average_precision_score(yy, prob):.2f})")
    a1.plot([0, 1], [0, 1], "k--", lw=1)
    a1.set(xlabel="False positive rate", ylabel="True positive rate", title="ROC curve: any category ran short")
    a2.axhline(yy.mean(), color="k", ls="--", lw=1, label=f"base rate {yy.mean():.2f}")
    a2.set(xlabel="Recall", ylabel="Precision", title="Precision-recall curve: any category ran short")
    a1.legend(fontsize=8)
    a2.legend(fontsize=8)
    save(fig, out / "fig_roc_pr_shortage.png")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- report
def md_table(d: pd.DataFrame, cols, fmt="{:.3f}") -> str:
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in d.iterrows():
        lines.append("| " + " | ".join(fmt.format(r[c]) if isinstance(r[c], float) else str(r[c]) for c in cols)
                     + " |")
    return "\n".join(lines)


def write_report(out, df, reg, hd, sh, winners):
    w = pd.DataFrame([{"category": c, "expected": MODEL_LABEL[v["expected"]], "safe": MODEL_LABEL[v["safe"]]}
                      for c, v in winners.items()])
    all_reg = reg[reg.subset == "all"].copy()
    all_reg["model"] = all_reg.model.map(MODEL_LABEL)
    hd2 = hd.copy()
    hd2["model"] = hd2.model.map(MODEL_LABEL)
    sh_all = sh[sh.subset == "all"].copy()
    sh_all["model"] = sh_all.model.map(CLF_LABEL)

    text = f"""# Food Model Evaluation

Generated by `python src/evaluate.py` from `data/processed/master.csv`: {len(df)} events.
Every number is out-of-fold from 5-fold cross-validation, so each event is scored by a model that
never saw it.

## Winners (used by the app, `models/winners.json`)
{md_table(w, ["category", "expected", "safe"])}

The expected-quantity winner is the model with the lowest MAE in kg per category. The safe quantity
is the quantile GBM at P85.

## 1. Quantity models: all events
{md_table(all_reg, ["category", "model", "n", "mae_kg", "rmse_kg", "r2", "r2_per_guest", "mape_pct", "coverage"])}

`r2` is on kg per event, so it is high mostly because bigger events eat more. `r2_per_guest` is on
the target itself (eaten per guest) and shows how much the features add beyond the guest count.
`coverage` = share of events where the predicted amount was enough (target 0.85 for the P85 model).

![](fig_model_comparison_mae.png)
![](fig_predicted_vs_actual.png)
![](fig_residuals.png)
![](fig_p85_coverage.png)
![](fig_learning_curves.png)
![](fig_feature_importance.png)

## 2. High-demand detection (regression output as a yes/no call)
High demand = eaten per guest above the median for that category.
{md_table(hd2, ["target", "model", "n", "positives", "accuracy", "precision", "recall", "f1"])}

![](fig_confusion_high_demand.png)

## 3. Shortage risk classification (will food run short?)
Booking-time features only. Positive class = ran short. Threshold 0.5, classes balanced in training.
{md_table(sh_all, ["target", "model", "n", "positives", "accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc"])}

![](fig_confusion_shortage.png)
![](fig_confusion_shortage_by_category.png)
![](fig_roc_pr_shortage.png)

## Reading the results
- `r2_per_guest` near 0 means the booking-time features explain little of how much each guest eats beyond the
  average. The chef's rule (average per guest) is hard to beat on plain error.
- The gain comes from the safe quantity: the P85 model reaches about 0.83 coverage and has the
  lowest shortage-weighted cost (see `python src/train.py` output).
- "Never short" gets high accuracy with zero recall: accuracy alone is misleading when shortages are
  rare, so compare models on recall, F1 and ROC-AUC.
"""
    (out / "RESULTS.md").write_text(text, encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="data/processed/master.csv")
    p.add_argument("--out", default="results/category_models")
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(a.data)
    df = df[df.guests_actual > 0].reset_index(drop=True)
    X, Y = build_features(df), compute_targets(df)
    winners = json.loads((MODELS_DIR / "winners.json").read_text(encoding="utf-8"))
    oof = pd.read_csv(out / "oof_predictions.csv")

    reg = regression_metrics(oof)
    reg.to_csv(out / "metrics_regression.csv", index=False)
    plot_model_comparison(reg, out)
    plot_pred_vs_actual(oof, winners, out)
    plot_residuals(oof, winners, out)
    plot_coverage(reg, out)
    plot_learning_curves(X, Y, winners, out)
    plot_feature_importance(out)

    hd = high_demand(oof, out)
    hd.to_csv(out / "metrics_high_demand.csv", index=False)
    sh = shortage(df, X, out)
    sh.to_csv(out / "metrics_shortage.csv", index=False)

    write_report(out, df, reg, hd, sh, winners)
    pd.set_option("display.width", 200)
    print(reg[reg.subset == "all"].round(3).to_string(index=False))
    print()
    print(sh[(sh.subset == "all") & (sh.target == "any")].round(3).to_string(index=False))
    print(f"\nWrote metrics, figures and {out / 'RESULTS.md'}")


if __name__ == "__main__":
    main()
