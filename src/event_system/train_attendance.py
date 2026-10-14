"""Train the attendance model used by the event-order app.

Quantile regression (the best-calibrated safe method in the research, see results/attendance/RESULTS.md)
is fitted for safety levels P50 to P95 on the real events. It predicts attendance_ratio = actual / booked
from booked size, weekend, month and road km from the client's town.

Each level is also back-tested with leave-one-event-out, so the app can show what that level would have
done on the past events (estimated leftover kg and how often food ran short).

Writes models/attendance_quantreg.json: scaler, coefficients per level and the back-test. It holds model
coefficients and totals only, no event rows.

Usage: python src/event_system/train_attendance.py data/processed/events_clean.csv models/attendance_quantreg.json
"""
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

warnings.filterwarnings("ignore")
FEATURES = ["log_booked", "weekend", "month_sin", "month_cos", "road_km"]
LEVELS = [round(x, 2) for x in np.arange(0.50, 0.951, 0.05)]


def prepare(d):
    d = d.copy()
    d["log_booked"] = np.log(d.pax_booked)
    d["month_sin"] = np.sin(2 * np.pi * d.month / 12)
    d["month_cos"] = np.cos(2 * np.pi * d.month / 12)
    d["weekend"] = d.weekend.astype(int)
    return d


def fit(d, q):
    mu, sd = d[FEATURES].mean(), d[FEATURES].std(ddof=0).replace(0, 1)
    X = sm.add_constant(((d[FEATURES] - mu) / sd).values, has_constant="add")
    res = sm.QuantReg(d.attendance_ratio.values, X).fit(q=q, max_iter=5000)
    return mu, sd, res.params


def predict(mu, sd, params, rows):
    X = sm.add_constant(((rows[FEATURES] - mu) / sd).values, has_constant="add")
    return X @ params


def main(src, out):
    d = pd.read_csv(src)
    d = prepare(d[d.usable == 1].sort_values(["date", "event_id"], kind="stable").reset_index(drop=True))
    model = dict(features=FEATURES, n_events=int(len(d)), levels={}, backtest={},
                 chef_rule=dict(leftover_kg=float(d.leftover_est_kg.sum()), short_events=int(d.ran_short.sum())))
    mu, sd, _ = fit(d, 0.5)
    model["mean"], model["std"] = mu.tolist(), sd.tolist()
    for q in LEVELS:
        model["levels"][f"{q:.2f}"] = fit(d, q)[2].tolist()
        # leave-one-event-out back-test of this level
        cook, left, short = [], 0.0, 0
        for i in range(len(d)):
            tr, te = d.drop(index=i), d.iloc[[i]]
            k = predict(*fit(tr, q), te)[0]
            pax = max(1.0, round(k * te.pax_booked.iloc[0]))
            missing = pax - te.pax_actual.iloc[0]
            left += max(0.0, missing) * te.kg_per_no_show.iloc[0]
            short += int(missing < 0)
            cook.append(pax)
        model["backtest"][f"{q:.2f}"] = dict(leftover_kg=round(left, 1), short_events=short)
        print(f"P{int(q*100)}: leftover {left:6.1f} kg, short {short:2d} of {len(d)}")
    model["ratio_quantiles"] = {f"{q:.2f}": float(d.attendance_ratio.quantile(q)) for q in LEVELS}
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as fh:
        json.dump(model, fh, indent=1)
    print(f"chef rule: leftover {model['chef_rule']['leftover_kg']:.1f} kg, short {model['chef_rule']['short_events']}")
    print(f"saved {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/processed/events_clean.csv",
         sys.argv[2] if len(sys.argv) > 2 else "models/attendance_quantreg.json")
