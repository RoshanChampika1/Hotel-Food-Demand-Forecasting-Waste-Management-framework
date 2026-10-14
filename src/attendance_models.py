"""Attendance-based food planning: model comparison with leave-one-event-out validation.

Question: the chef cooks for the booked guest count. Guests who do not come leave food behind
(0.5-0.65 kg each); extra guests make food run short and force re-cooking. Can a model choose a
better number of guests to cook for?

Every method predicts a "cook-for ratio" k for an event. The kitchen cooks for booked x k guests.
  leftover kg  = max(cooked_for - actual, 0) x kg_per_no_show
  shortfall    = actual > cooked_for (food runs out, kitchen re-cooks)

Usage: python run_models.py <events_clean.csv> <out_dir>
"""
import os, sys, warnings
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from xgboost import XGBRegressor
import statsmodels.api as sm

warnings.filterwarnings("ignore")
RNG = np.random.default_rng(42)
Q = 0.85                    # target coverage for the "safe" quantity
RAW_COST_PER_PAX = 675.40   # LKR, hotel's own costing sheet
FEATURES = ["log_booked", "night", "weekend", "n_dishes_total", "month_sin", "month_cos", "wedding", "road_km"]


def load(path):
    d = pd.read_csv(path)
    d = d[d.usable == 1].copy().sort_values(["date", "event_id"], kind="stable").reset_index(drop=True)
    d["log_booked"] = np.log(d.pax_booked)
    d["night"] = (d.session == "night").astype(int)
    d["wedding"] = (d.event_type == "wedding").astype(int)
    d["month_sin"] = np.sin(2 * np.pi * d.month / 12)
    d["month_cos"] = np.cos(2 * np.pi * d.month / 12)
    d["weekend"] = d.weekend.astype(int)
    return d


# ---------- methods: each takes (train df, test row df) and returns predicted ratio k ----------
def chef(tr, te):
    return np.ones(len(te))


def mean_ratio(tr, te):
    return np.full(len(te), tr.attendance_ratio.mean())


def emp_quantile(q):
    def f(tr, te):
        return np.full(len(te), np.quantile(tr.attendance_ratio, q))
    return f


def sk_model(make):
    def f(tr, te):
        m = make().fit(tr[FEATURES], tr.attendance_ratio)
        return m.predict(te[FEATURES])
    return f


def ridge():
    return make_pipeline(StandardScaler(), Ridge(alpha=10.0))


def linreg():
    return make_pipeline(StandardScaler(), LinearRegression())


def rf():
    return RandomForestRegressor(n_estimators=300, max_depth=3, min_samples_leaf=5, random_state=0)


def gbm():
    return GradientBoostingRegressor(n_estimators=100, max_depth=2, learning_rate=0.05, min_samples_leaf=5, random_state=0)


def gbm_q(q):
    return lambda: GradientBoostingRegressor(loss="quantile", alpha=q, n_estimators=100, max_depth=2,
                                             learning_rate=0.05, min_samples_leaf=5, random_state=0)


def xgb():
    return XGBRegressor(n_estimators=100, max_depth=2, learning_rate=0.05, min_child_weight=5,
                        subsample=0.8, reg_lambda=1.0, random_state=0, n_jobs=1)


def xgb_q(q):
    return lambda: XGBRegressor(objective="reg:quantileerror", quantile_alpha=q, n_estimators=100, max_depth=2,
                                learning_rate=0.05, min_child_weight=5, subsample=0.8, random_state=0, n_jobs=1)


QR_FEATURES = ["log_booked", "weekend", "month_sin", "month_cos", "road_km"]  # fewer features: quantile regression is unstable at small n


def quant_reg(q):
    def f(tr, te):
        sc = StandardScaler().fit(tr[QR_FEATURES])
        X = sm.add_constant(sc.transform(tr[QR_FEATURES]), has_constant="add")
        Xt = sm.add_constant(sc.transform(te[QR_FEATURES]), has_constant="add")
        res = sm.QuantReg(tr.attendance_ratio.values, X).fit(q=q, max_iter=5000)
        return Xt @ res.params
    return f


def conformal(base, q):
    """Jackknife+-style safe quantity: base prediction + q-quantile of the base model's own
    leave-one-out residuals on the training events (finite-sample corrected)."""
    def f(tr, te):
        res = []
        for i in range(len(tr)):
            inner_tr = tr.drop(tr.index[i])
            res.append(tr.attendance_ratio.iloc[i] - base(inner_tr, tr.iloc[[i]])[0])
        res = np.sort(res)
        n = len(res)
        k = min(int(np.ceil(q * (n + 1))) - 1, n - 1)
        return base(tr, te) + res[k]
    return f


METHODS = {
    # expected-attendance methods
    "Chef rule (cook for booked)": ("baseline", chef),
    "Average ratio": ("expected", mean_ratio),
    "Median ratio": ("expected", emp_quantile(0.5)),
    "Linear regression": ("expected", sk_model(linreg)),
    "Ridge regression": ("expected", sk_model(ridge)),
    "Random forest (shallow)": ("expected", sk_model(rf)),
    "Gradient boosting (shallow)": ("expected", sk_model(gbm)),
    "XGBoost (shallow)": ("expected", sk_model(xgb)),
    # safe (85%) methods
    "Safe: 85th percentile of past ratios": ("safe", emp_quantile(Q)),
    "Safe: quantile regression P85": ("safe", quant_reg(Q)),
    "Safe: Ridge + conformal margin P85": ("safe", conformal(sk_model(ridge), Q)),
    "Safe: quantile GBM P85": ("safe", sk_model(gbm_q(Q))),
    "Safe: XGBoost quantile P85": ("safe", sk_model(xgb_q(Q))),
}


def outcomes(d, k):
    cooked = d.pax_booked.values * k
    actual = d.pax_actual.values
    leftover_pax = np.maximum(cooked - actual, 0)
    short_pax = np.maximum(actual - cooked, 0)
    return pd.DataFrame({
        "event_id": d.event_id.values, "k": k, "cooked_for": cooked, "actual": actual,
        "abs_err_guests": np.abs(cooked - actual),
        "leftover_kg": leftover_pax * d.kg_per_no_show.values,
        "leftover_kg_low": leftover_pax * 0.5, "leftover_kg_high": leftover_pax * 0.65,
        "leftover_lkr": leftover_pax * RAW_COST_PER_PAX,
        "short": (short_pax > 0.5).astype(int), "short_guests": short_pax,
        "pinball": np.where(actual >= cooked, Q * (actual - cooked), (1 - Q) * (cooked - actual)),
    })


def loeo(d, fn):
    k = np.empty(len(d))
    for i in range(len(d)):
        k[i] = fn(d.drop(d.index[i]), d.iloc[[i]])[0]
    return k


def boot_ci(x, n=2000):
    idx = RNG.integers(0, len(x), (n, len(x)))
    s = x[idx].sum(1)
    return np.percentile(s, [2.5, 97.5])


def summarise(name, kind, o, base):
    lo, hi = boot_ci(o.leftover_kg.values)
    diff = base.leftover_kg.values - o.leftover_kg.values
    dlo, dhi = boot_ci(diff)
    try:
        p = stats.wilcoxon(base.abs_err_guests, o.abs_err_guests).pvalue if not np.allclose(base.abs_err_guests, o.abs_err_guests) else np.nan
    except ValueError:
        p = np.nan
    return {
        "method": name, "type": kind,
        "MAE_guests": o.abs_err_guests.mean(),
        "leftover_kg_total": o.leftover_kg.sum(), "leftover_kg_95CI": f"{lo:.0f}-{hi:.0f}",
        "leftover_kg_range_0.5-0.65": f"{o.leftover_kg_low.sum():.0f}-{o.leftover_kg_high.sum():.0f}",
        "leftover_LKR": o.leftover_lkr.sum(),
        "kg_saved_vs_chef": diff.sum(), "kg_saved_95CI": f"{dlo:.0f} to {dhi:.0f}",
        "shortfall_events": int(o.short.sum()), "shortfall_rate": o.short.mean(),
        "coverage": 1 - o.short.mean(),
        "short_guests_total": o.short_guests.sum(),
        "pinball_P85": o.pinball.mean(),
        "wilcoxon_p_vs_chef_abs_err": p,
    }


def tradeoff(d):
    """Leftover vs shortfall for a range of safety levels (no-feature empirical quantile and Ridge+conformal)."""
    rows = []
    for q in np.round(np.arange(0.40, 0.96, 0.05), 2):
        for label, fn in (("Past-ratio percentile", emp_quantile(q)), ("Ridge + conformal", conformal(sk_model(ridge), q))):
            o = outcomes(d, loeo(d, fn))
            rows.append({"method": label, "q": q, "leftover_kg": o.leftover_kg.sum(),
                         "shortfall_rate": o.short.mean(), "shortfall_events": int(o.short.sum())})
    return pd.DataFrame(rows)


def time_split(d, frac=0.6):
    """Robustness: train on the earliest events, test on the later ones (as the hotel would use it)."""
    n = int(len(d) * frac)
    tr, te = d.iloc[:n], d.iloc[n:]
    rows = []
    for name, (kind, fn) in METHODS.items():
        o = outcomes(te, fn(tr, te))
        rows.append({"method": name, "test_events": len(te), "MAE_guests": o.abs_err_guests.mean(),
                     "leftover_kg": o.leftover_kg.sum(), "shortfall_events": int(o.short.sum())})
    return pd.DataFrame(rows), tr.date.max(), te.date.min()


def plots(d, res, trade, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, muted, grid = "#0b0b0b", "#52514e", "#e4e3df"
    blue, orange, aqua = "#2a78d6", "#eb6834", "#1baf7a"
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": muted, "axes.labelcolor": ink,
                         "xtick.color": muted, "ytick.color": muted, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.dpi": 150})

    # 1. Distribution of attendance ratio
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    ax.hist(d.attendance_ratio, bins=np.arange(0.86, 1.36, 0.02), color=blue, edgecolor="white", linewidth=1.5)
    ax.axvline(1.0, color=ink, linewidth=1.5, linestyle="--")
    ax.text(1.005, ax.get_ylim()[1] * 0.92, "Chef cooks for booked (1.00)", color=ink, fontsize=9)
    q85 = np.quantile(d.attendance_ratio, Q)
    ax.axvline(q85, color=orange, linewidth=1.5)
    ax.text(q85 + 0.005, ax.get_ylim()[1] * 0.78, f"85th percentile ({q85:.2f})", color=ink, fontsize=9)
    ax.set_xlabel("Actual guests ÷ booked guests")
    ax.set_ylabel("Number of events")
    ax.set_title(f"How many booked guests actually came ({len(d)} events)", loc="left", fontsize=11, color=ink)
    ax.grid(axis="y", color=grid, linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig1_attendance_ratio.png"))
    plt.close(fig)

    # 2. Trade-off curve
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    for (label, g), col in zip(trade.groupby("method", sort=False), (blue, aqua)):
        ax.plot(g.shortfall_rate * 100, g.leftover_kg, color=col, linewidth=2, marker="o", markersize=5, label=label)
        if label != "Past-ratio percentile":
            continue
        for _, r in g[g.q.isin([0.5, 0.7, 0.85])].iterrows():
            ax.annotate(f"P{int(r.q * 100)}", (r.shortfall_rate * 100, r.leftover_kg), textcoords="offset points",
                        xytext=(6, 4), fontsize=8, color=muted)
    c = res[res.method.str.startswith("Chef")].iloc[0]
    ax.scatter([c.shortfall_rate * 100], [c.leftover_kg_total], s=90, color=orange, zorder=5, edgecolor="white", linewidth=2,
               label="Chef rule (today)")
    ax.set_xlabel("Events where food ran short (%)")
    ax.set_ylabel("Estimated leftover food (kg, all events)")
    ax.set_title("Waste vs running-short trade-off (leave-one-event-out)", loc="left", fontsize=11, color=ink)
    ax.grid(color=grid, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig2_tradeoff.png"))
    plt.close(fig)


def main(src, out):
    os.makedirs(out, exist_ok=True)
    d = load(src)
    per_event, rows = {}, []
    for name, (kind, fn) in METHODS.items():
        per_event[name] = outcomes(d, loeo(d, fn))
    base = per_event["Chef rule (cook for booked)"]
    for name, (kind, fn) in METHODS.items():
        rows.append(summarise(name, kind, per_event[name], base))
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(out, "results_loeo.csv"), index=False)
    pd.concat({k: v for k, v in per_event.items()}, names=["method"]).reset_index(level=0).to_csv(
        os.path.join(out, "per_event_predictions.csv"), index=False)

    trade = tradeoff(d)
    trade.to_csv(os.path.join(out, "tradeoff.csv"), index=False)
    ts, last_train, first_test = time_split(d)
    ts.to_csv(os.path.join(out, "results_time_split.csv"), index=False)

    # feature check: does anything explain attendance?
    corr = d[["attendance_ratio"] + FEATURES].corr()["attendance_ratio"].drop("attendance_ratio")
    corr.to_csv(os.path.join(out, "feature_correlations.csv"))
    plots(d, res, trade, out)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    print(f"events: {len(d)}")
    print(res[["method", "MAE_guests", "leftover_kg_total", "leftover_kg_95CI", "leftover_LKR", "kg_saved_vs_chef",
               "kg_saved_95CI", "shortfall_events", "coverage", "pinball_P85", "wilcoxon_p_vs_chef_abs_err"]].round(3).to_string())
    print("\ntrade-off\n", trade.round(3).to_string())
    print(f"\ntime split (train to {last_train}, test from {first_test})\n", ts.round(2).to_string())
    print("\ncorrelations\n", corr.round(3))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
