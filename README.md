# Hotel Food Demand Forecasting System

A machine learning system that predicts per-category food quantities for
hotel banquet events, to reduce over-catering waste while avoiding the
higher cost of running short — final-year undergraduate research project.

## Student Details

| Field                 | Value                                                    |
| --------------------- | -------------------------------------------------------- |
| NIBM Registered Name  | CHAMPIKA H R                                             |
| NIBM Index Number     | COBSCCOMP242P-064                                        |
| Coventry Index Number | 16110795                                                 |
| Programme             | BSc (Hons) Computer Science — Coventry University (NIBM) |

## Overview

Hotels planning banquet events (weddings, corporate functions, conferences,
etc.) currently rely on staff experience to decide how much food to
prepare per category. Over-preparing wastes food and money; under-preparing
risks running out mid-event, which carries a reputational and operational
cost that a simple surplus does not. This project builds a data-driven
forecasting pipeline that predicts, from information known at booking
time, both an **expected** quantity and a **safe** quantity per food
category — giving hotel staff a defensible number instead of a guess.

Primary data source is the author's own hotel in Sri Lanka, supplemented
by real banquet event records currently being collected from 3-4 partner
hotels.

## Problem Statement

Manual, experience-based food quantity planning for banquet events leads
to inconsistent outcomes — some events over-cater and generate food waste,
others under-cater and run short. There is no standardized, data-driven
method in use at these hotels to estimate food demand per category ahead
of an event, nor any explicit accounting for the fact that running short
is costlier than an equivalent surplus.

## Research Objectives

1. Collect and structure real banquet event data (bookings, guest counts,
   food prepared/consumed/leftover) across multiple hotels into a common
   schema.
2. Engineer booking-time-only features (no information that would only be
   known after the event) suitable for a small tabular dataset.
3. Compare a chef's-rule baseline against multiple regression approaches
   (linear regression, gradient boosted trees, random forest) for
   predicting per-guest food consumption by category.
4. Produce a **safe quantity** estimate via quantile regression (85th
   percentile) that explicitly accounts for the asymmetric cost of running
   short vs. over-preparing — the project's central research contribution.
5. Deliver a usable interface (Streamlit) so hotel staff can get a
   prediction for a new event without touching code or data files.

## Key Research Contribution

The core claim under test: **a quantile-regression "safe quantity" reduces
real-world cost more than a model chosen purely to minimize average
error**, because average error treats a kg of waste and a kg of shortage
as equally bad, when they are not.

On the combined dataset (554 events, 5-fold cross-validation, see
[results/category_models/RESULTS.md](results/category_models/RESULTS.md)), the 85th-percentile model
has the lowest shortage-weighted cost in every food category, despite having a _worse_ average error
than the point-estimate models. That is the expected signature of this approach working as intended.

## Current Status



| Component                                                            | Status |
| -------------------------------------------------------------------- | ------ |
| Combined dataset (`data/combined/all_events.csv` + `.xlsx`)           | Done   |
| Preprocessing + QC report (`src/preprocess.py`)                      | Done   |
| Booking-time feature engineering                                     | Done   |
| Model training + winner selection (`src/train.py`)                   | Done   |
| Full evaluation: error metrics, confusion matrices, F1, ROC/PR, learning curves (`src/evaluate.py`) | Done |
| Single-event and batch prediction                                    | Done   |
| Streamlit app                                                        | Done   |
| Real-data attendance analysis (`src/event_orders/`)                  | Done: see [results/attendance/RESULTS.md](results/attendance/RESULTS.md) (analysis script no longer in the repo) |
| Event Order System app (`src/event_system/`, `app/streamlit_app.py`)  | Done: Party Menu → safe guest count → Stock Balance → printable PDFs/Excel ([docs/event_order_system.md](docs/event_order_system.md)) |

## Methodology

- **Target variable**: consumed-per-guest rate, `(prepared − leftover) /
guests_actual`, computed per food category and scaled by guest count at
  prediction time. Normalizes across differently-sized events and across
  hotels.
- **Categories** (aggregate, not individual dishes — menu-level detail is
  not obtainable consistently across partner hotels): rice & starch,
  mains, vegetable sides, desserts, beverages.
- **Features**: booking-time information only (event type, meal type,
  guest count, weekend flag, season) — nothing derived from the event
  outcome, to avoid data leakage.
- **Models**: chef's-rule mean baseline, linear regression, gradient
  boosted trees (primary model), quantile gradient boosting at the 85th
  percentile (safe quantity), random forest (comparison). Deep learning
  was deliberately excluded — the dataset (150-400 real rows expected) is
  small and tabular, where classical models are the appropriate and
  defensible choice.
- **Evaluation**: 5-fold cross-validation rather than a single train/test
  split, given the small sample size. Reports mean absolute error (both
  per-guest and absolute-quantity scale), 85th-percentile calibration
  (empirical coverage), feature importance, and a cost-based comparison
  under an asymmetric shortage/surplus cost assumption.
- **Data quality tracking**: every record carries a quality flag
  (Recorded / Manual estimate / Eyeballed) which is preserved through the
  full pipeline and used for a records-only robustness check.

## Technology Stack

Python, pandas, scikit-learn, Streamlit. Deliberately no deep learning
framework, no database, no web framework beyond Streamlit — the dataset
size and project scope do not justify the added complexity.

## Repository Structure

```
src/features.py              shared feature engineering (booking-time only),
                              imported by both training and prediction
src/preprocess.py            cleans data/combined/all_events.csv into data/processed/master.csv + reports/qc_report.md
src/train.py                 trains all models for all categories, picks the winners,
                              saves models/*.joblib + models/winners.json
src/evaluate.py              metrics, confusion matrices and curves ->
                              results/category_models/
src/predict.py                predict_event(dict) — single-event inference,
                              used by the app
app/streamlit_app.py         input form -> expected + safe quantities
docs/food_demand_dataset_template.xlsx   data collection template used by
                              partner hotels
data/combined/all_events.csv the combined event table (pipeline input; also .xlsx)
data/raw/, data/processed/   real hotel data (gitignored — not in this repo,
                              confidential)
models/                      trained model artifacts (gitignored, regenerated
                              from data)
```

Real hotel data and trained models are excluded from version control for
confidentiality — see `.gitignore`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the Pipeline

```bash
# Input: data/combined/all_events.csv (one row per event)

# 1. Clean it (writes data/processed/master.csv and reports/qc_report.md)
python src/preprocess.py

# 2. Train all 5 categories x 5 models and pick the winners
python src/train.py

# 3. Evaluation: metrics, confusion matrices, ROC/PR and learning curves
python src/evaluate.py

# 4. Single-event inference sanity check, then the app
python src/predict.py
streamlit run app/streamlit_app.py
```

The app picks up newly trained models and winners automatically — no code changes needed.
See [docs/dataset.md](docs/dataset.md) for the columns of the combined table.

## Real-Data Analysis (October 2026)

Real data came from the hotel's own **event-order workbooks** (menu, booked guests, actual guest count, chef's planned raw materials), not from the per-category leftover template. They do not record leftover per food category, so the analysis models what drives waste in practice: **the gap between booked and actual guests**. The chef cooks for the booked count, each missing guest leaves about 0.5–0.65 kg of food, and extra guests make food run short until the kitchen re-cooks.

```bash
# Put the private event-order .xlsx files in data/raw/ (git-ignored), and the
# town distance file in data/inputs/town_distance.csv (git-ignored), then:
python src/event_orders/extract_events.py data/raw data/processed
python src/event_orders/build_dataset.py data/raw data/processed
```

The attendance results in `results/attendance/` come from an earlier analysis script that is no
longer in the repository; the committed CSVs and charts are kept as they were.

- Leave-one-event-out comparison of the chef's rule, average and median ratio, linear and Ridge regression, random forest, gradient boosting, and P85 safe methods (quantile regression, conformal margin, quantile GBM)
- A waste vs running-short trade-off curve, a train-on-past / test-on-future check, and a road-distance feature test
- Findings, in plain English: [results/attendance/RESULTS.md](results/attendance/RESULTS.md)
- Step-by-step VS Code guide: [docs/RUN_IN_VSCODE.md](docs/RUN_IN_VSCODE.md)
- Data dictionary: [docs/event_order_data.md](docs/event_order_data.md); project plan and viva preparation: [docs/plan/](docs/plan/)

Only aggregate results are committed. Event-level data stays private, in line with the policy below.

## Event Order System (the app)

The app replaces the manual Excel event order. Staff enter the event (date, day/night, hall, type,
serving time, booked pax, customer town), choose dishes for the Party Menu, and get the Stock Balance
(Fresh, Dry and Meat items) and kitchen recipes. The number of guests to cook for comes from the
attendance model at a chosen safety level. The Party Menu, Stock Balance and kitchen recipes download
as separate PDFs, or together as one Excel file.

```bash
python src/event_system/build_master_data.py data/raw data/master      # recipe book, dishes, items (private)
python src/event_system/train_attendance.py                              # guest-count model
streamlit run app/streamlit_app.py
```

Design and checks: [docs/event_order_system.md](docs/event_order_system.md).

## Running It for Hotel Staff (Not Just Local Dev)

For actual day-to-day use at the hotel rather than local demoing, bind the
app to the machine's network address so anyone on the same hotel WiFi/LAN
can open it:

```bash
streamlit run app/streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

Share `http://<machine's-LAN-IP>:8501` with staff, and keep the process
running (e.g. via `tmux`/`screen`, or a login item) on a machine that
stays on. This stays LAN-only rather than a public cloud deployment,
consistent with the project's deliberately simple, dependency-light scope.

## Data & Privacy

Real hotel data and any models trained on it are excluded from version
control (`.gitignore`) and never leave the author's machine as part of
this repository. Data
quality is tracked explicitly per record (Recorded / Manual estimate /
Eyeballed) so the reliability of the underlying data is never hidden
behind a single aggregate metric.

## Limitations & Future Work

- Real events record one leftover estimate per event (split across categories) and no beverages;
  more weighed, per-category records would sharpen the per-category models.
- The illustrative cost ratio used to compare models (shortage vs.
  surplus cost per kg) is a placeholder pending a real estimate from the
  hotel.
- The safe-quantity model's calibration (does the 85th-percentile
  prediction actually cover ~85% of outcomes?) needs re-validating on
  real data.
- Booking-time features explain little of per-guest consumption beyond the average; richer
  booking features (menu size, package rate) are the natural next step.
