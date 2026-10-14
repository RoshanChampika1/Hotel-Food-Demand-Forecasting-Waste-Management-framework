# Rescue Plan: Finish the Research by 20 October

Written 11 October 2026. You have 9 working days and 30 real event records.

---

## 1. The honest situation (read this first)

- 30 events is **small, but it is enough for a pilot study**. Many published food-waste and hospitality studies use 20 to 60 cases. What matters is that you are honest about it and choose methods that fit small data.
- You **cannot** honestly claim "our ML model beats everything" with 30 events. You **can** honestly show:
  1. A working end-to-end system (data → model → safe quantity → app).
  2. A fair, careful comparison of simple methods on real data.
  3. How much food the system *would have saved* on your 30 real events.
  4. How accuracy is expected to improve as more data is collected (simulation study).
- That is a complete, defensible final-year project. Examiners usually reward **honesty and sound method** more than big accuracy numbers.

**Key mindset change:** your project is no longer "a big ML forecasting system". It is **"a small-data, uncertainty-aware food forecasting framework, tested as a pilot on 30 real banquet events"**. This framing turns your weakness (little data) into the research topic itself.

---

## 2. New research framing (rescope)

### Suggested title
> *A Small-Data, Risk-Aware Approach to Forecasting Banquet Food Demand for Waste Reduction: A Pilot Study*

### Research question (main)
> Can a simple, risk-aware forecasting method recommend banquet food quantities that reduce overproduction compared to the chef's current rule, without increasing the risk of running short, when only a small number of past events are available?

### Sub-questions
1. Which simple model predicts consumed-food-per-guest best with very little data?
2. Can a "safe quantity" (P85) give enough food 85% of the time while still cutting waste?
3. How many events would a hotel need to collect before the model becomes reliable? (answered by the simulation study)

### What stays from the original design
- Predict **consumed per guest** for the 5 categories, then multiply by guest count. (This is even more important now, because it lets different-sized events be compared.)
- The **chef's-rule baseline** (average per guest).
- The **P85 safe quantity** idea. It is still your key novelty.
- The R/M/E data quality flags and the `ran_short` flag.
- The Streamlit app.

### What changes
| Before | After | Why (viva answer) |
|---|---|---|
| Gradient boosting as main model | **Ridge regression and linear quantile regression as main models**; GBM and RF kept only as comparisons | Tree ensembles need hundreds of rows. With 30 events they memorise the data (overfit). Simple models are the correct choice for small n. |
| Quantile GBM for P85 | **Linear quantile regression at 0.85 + a conformal "safety margin" (jackknife+)** | Quantile GBM is unstable at n=30. Conformal prediction gives a mathematically backed coverage guarantee even with small data. |
| Train/test split (e.g. 80/20) | **Leave-one-event-out cross-validation** | A 20% test set would be only 6 events, which is too few to trust. Leave-one-out uses every event as a test once. |
| 150–400 events target | **30 real events (pilot) + simulation study** | Data access limits are a real-world finding in themselves, and you report them. |

---

## 3. How to use 30 events as well as possible

### 3.1 Turn 30 events into 150 rows (correctly)
Each event has 5 food categories. Store the data in **long format**: one row = one event × one category, so 30 × 5 = 150 rows. Add `category` as a feature.

- This lets one model learn from all categories together, instead of 5 tiny models with 30 rows each.
- **Important:** the 5 rows from one event are related. So when testing, always hold out **all 5 rows of an event together** (this is called *grouped* cross-validation). If you don't, the model "sees" part of the test event during training and the results look better than they really are. Saying this at the viva shows you understand data leakage.

### 3.2 Use very few features
Rule of thumb: about **10 events per feature**. With 30 events, use **3 to 5 features**. Good candidates (pick the ones you actually have):
1. Event type (wedding / corporate / birthday / other) — group rare types into "other".
2. Meal time (lunch / dinner).
3. Service style (buffet / plated), if it varies.
4. Number of dishes in that category on the menu.
5. Weekend or weekday.

Do not use many dummy variables or fine-grained details. Fewer features = less overfitting = easier to explain.

### 3.3 Check the data quality flags
- Report how many of the 30 are R (records), M (mixed), E (estimated).
- Run the main result twice: **all events** vs **records-only (R) events**. If both tell the same story, your result is robust. This is a strong viva point.
- Events with `ran_short = yes`: consumption is *capped* (guests would have eaten more). Either remove them from training for the expected-value model, or keep them and flag them in the discussion. Recommended default: **keep them, but mark them and report their count**, and do one sensitivity run without them.

---

## 4. Methods that are defensible with very small n

### 4.1 The model line-up (final)
| # | Model | Role | Why it's defensible |
|---|---|---|---|
| 1 | Chef's rule: average per guest (overall, per category) | Baseline = current practice | This is what kitchens do today |
| 2 | Chef's rule by event type: average per guest per event type | Stronger baseline | Fair, simple, hard to beat |
| 3 | **Ridge regression** | Main "expected quantity" model | Linear and stable; the penalty prevents overfitting with few rows |
| 4 | **Linear quantile regression (q = 0.85)** | Main "safe quantity" model | Directly predicts the 85th percentile; easy to explain |
| 5 | **Ridge + conformal margin (jackknife+)** | Alternative safe quantity | Gives coverage guarantee without assuming normal errors |
| 6 | Random forest (shallow, e.g. max_depth 3) | Comparison only | Shows what happens with complex models on small data |
| 7 | Gradient boosting / quantile GBM (shallow) | Comparison only | Same; expected to overfit, and that is a finding |

Deep learning stays excluded (already a defended decision).

**Expected result:** Ridge and the event-type baseline will probably be close. Trees will probably be worse or unstable. **That is fine and honest.** Your contribution is the *safe-quantity framework and the waste saving*, not "the most complex model wins".

### 4.2 The safe quantity in simple words
- Expected quantity = "on average, guests eat this much."
- Safe quantity (P85) = "prepare this much, and you will have enough about 85 times out of 100."
- Conformal / jackknife+ method: train the model leaving out each event, see how wrong it was each time, and add the size of the typical error (the 85th percentile of those errors) on top of the prediction. Because it is based on the model's real mistakes, the "85%" promise holds even with small data.

### 4.3 Evaluation (how to test)
- **Leave-one-event-out cross-validation (LOEO-CV):** 30 rounds. Each round trains on 29 events and predicts the 1 left out.
- **Metrics for expected quantity:** MAE in kg per guest and kg per event; MAPE optional.
- **Metrics for safe quantity:**
  - **Coverage:** % of events where safe quantity ≥ actual consumed. Target ≈ 85%.
  - **Shortfall rate:** % of events where it would have run short (= 100% − coverage).
  - **Pinball (quantile) loss** for P85.
  - **Average surplus (waste) in kg.**
- **Uncertainty around your results:** bootstrap 95% confidence intervals (resample events 1,000 times). With n=30, intervals will be wide — **report them anyway**; it is honest.
- **Is the difference real?** Wilcoxon signed-rank test, model errors vs baseline errors (paired, by event). Works for small samples and doesn't assume normal data.

### 4.4 The headline result: retrospective waste-saving simulation
This is the most powerful and easy-to-understand result. For each of the 30 real events:
1. You know what the kitchen **actually prepared** and what was **actually consumed**.
2. Your model (trained without that event) gives a **safe quantity**.
3. Compare:
   - Actual waste = prepared − consumed.
   - Model waste = safe quantity − consumed (if positive).
   - Did the model run short? (safe quantity < consumed)

Report: *"Over 30 real events, the system would have reduced surplus food by X kg (Y%), worth about LKR Z, while running short in N events compared to M in actual practice."*

That one sentence is what examiners will remember. Use a realistic cost per kg for each category from your own hotel's purchase prices.

---

## 5. Synthetic data: how to use it honestly

### The golden rule
> **Synthetic data is never used to measure accuracy. Every accuracy and waste number in the thesis comes from the 30 real events only.**

If you follow this rule and state it clearly, synthetic data is completely defensible.

### Three honest uses
1. **Testing the software pipeline** (you already have a generator for this). Say so in the implementation chapter.
2. **Simulation study (recommended, adds real research value):**
   - Fit a simple generator to your 30 real events: for each category, the mean and spread of per-guest consumption by event type, plus how categories move together (a *Gaussian copula*, e.g. the `GaussianCopulaSynthesizer` in the SDV library, or your own simple version).
   - Generate datasets of size 30, 60, 100, 200, 400.
   - Train the models on each size and test on a separate synthetic test set.
   - Plot a **learning curve**: error vs number of events, for Ridge vs GBM.
   - This answers sub-question 3: *"How many events does a hotel need to collect?"* It also shows *when* complex models would start to win, which supports your original design as future work.
   - Clearly label it in the thesis: "simulation calibrated on the pilot data; it shows trends, not real-world accuracy."
3. **Augmentation experiment (optional, only if time):** add synthetic rows to training only, test on real events with LOEO-CV. Report with vs without. If it doesn't help, say so; that is also a valid result.

### What NOT to do
- Do not mix synthetic rows into the test set.
- Do not report synthetic-data accuracy as if it were real.
- Do not use GANs / CTGAN: they need hundreds or thousands of rows to learn, and with 30 they just copy noise. Hard to defend.
- Do not use SMOTE: it is for classification class imbalance, not this problem.

### Viva answer to have ready
> "Synthetic data was generated from statistics of the real pilot data and used only for pipeline testing and a learning-curve simulation. All reported accuracy and waste figures are from the 30 real events, using leave-one-event-out cross-validation."

---

## 6. Getting a little more real data (only until 14 October)

More data helps, but **stop collecting at the end of 14 October**, whatever happens. After that, the dataset is frozen.

Fastest sources, in order:
1. **Your own hotel's old records.** You are the owner. Banquet event orders, purchase orders, kitchen production sheets and invoices from the past 12–24 months can often be reconstructed even if waste was not logged. Mark these as **M or E** quality. Even 20 extra events moves you from 30 to 50, which is meaningfully better.
2. **Events happening this week** at your hotel. Log them fully (weigh leftovers). These are R-quality records.
3. **Partner hotels: make the ask tiny.** Hotels refuse because they fear exposure and extra work. So:
   - Ask for **only 10 events**, and only **6 fields**: event type, meal time, guest count, and prepared + leftover per category (or just the kitchen's own sheet, which you transcribe yourself).
   - Promise **full anonymity** (hotel name never appears; "Hotel B") with a short letter signed by your supervisor.
   - Offer something back: a free one-page report of their own waste and estimated cost.
   - Give them a **48-hour window**, and visit in person if possible rather than emailing.
   - If anything arrives, use it as a **small external test set** ("does the model trained on my hotel work at another hotel?"). Even 5–10 events is a nice extra result. If nothing arrives, the project is still complete.

---

## 7. Day-by-day schedule

Write a little every day. Do not leave the thesis to the end.

| Day | Date | Coding / data | Writing |
|---|---|---|---|
| 1 | **Sun 11 Oct** | Upload the 30 records here. Send partner-hotel requests. Start pulling old records from your own hotel. | List chapter headings; note what's already written. |
| 2 | **Mon 12 Oct** | Clean data, convert to long format, check flags. Exploratory analysis: per-guest consumption by category and event type, plots. Pick final 3–5 features. | Methodology: data collection, flags, normalisation per guest. |
| 3 | **Tue 13 Oct** | Build the LOEO-CV evaluation harness. Run baselines + Ridge + linear quantile regression. | Methodology: models and why they suit small data. |
| 4 | **Wed 14 Oct** | Add jackknife+ safe quantity, shallow RF/GBM. **Data freeze at end of day.** | Literature review: tighten, add small-data and conformal prediction references. |
| 5 | **Thu 15 Oct** | Re-run everything on the frozen dataset. Bootstrap CIs, Wilcoxon tests, R-only robustness check, waste-saving simulation in kg and LKR. | Start Results chapter with real tables. |
| 6 | **Fri 16 Oct** | Simulation study (learning curve). Connect final model to the Streamlit app; take screenshots. | Finish Results; write Implementation/system chapter. |
| 7 | **Sat 17 Oct** | Freeze code. Clean up repo and README. | Discussion, limitations, future work. Introduction polish. |
| 8 | **Sun 18 Oct** | Fix only bugs. | **Full draft complete.** Abstract, conclusion. Send to supervisor if possible. |
| 9 | **Mon 19 Oct** | — | Buffer: formatting, references, figures, proofreading. Prepare viva Q&A sheet. |
| 10 | **Tue 20 Oct** | — | **Submit in the morning**, not at the last minute. |

**If you fall behind,** cut in this order (last cut first):
1. Augmentation experiment (optional anyway).
2. Shallow RF/GBM comparison.
3. Simulation study (reduce to just 3 sizes: 30, 100, 300).
4. App polish (a working form is enough).

**Never cut:** baselines, Ridge, P85 safe quantity, LOEO-CV, the waste-saving result, the limitations section.

---

## 8. Thesis structure (suggested)

1. **Introduction:** food waste problem in hotel banquets; why per-category safe quantity; research question.
2. **Literature review:** food demand forecasting, food waste in hospitality, quantile regression and asymmetric cost, small-data ML and conformal prediction.
3. **Methodology:** data collection protocol and its difficulties (this is a finding: hotels are reluctant to share), quality flags, normalisation, features, models, LOEO-CV, metrics, synthetic data rules.
4. **System design and implementation:** pipeline, feature module shared by training and inference, Streamlit app.
5. **Results:** baseline vs models; safe-quantity coverage; waste saving in kg and LKR; robustness (R-only); simulation learning curve.
6. **Discussion:** what works with small data; why simple beat complex; practical use by chefs.
7. **Limitations and future work:** n=30, one hotel, recall-based records, ran_short censoring; future data collection protocol, partner hotels, more complex models when n grows.
8. **Conclusion.**

---

## 9. Viva questions to prepare for

| Likely question | Short answer |
|---|---|
| "Only 30 events. Is that enough?" | It is a pilot study. I chose methods built for small data, used leave-one-out testing so every event is tested, and reported confidence intervals so the uncertainty is visible. The simulation shows how results should improve with more data. |
| "Why not deep learning / XGBoost as main model?" | They need hundreds or thousands of rows. With 30 they overfit. I tested shallow tree models and they confirmed this. |
| "Why per-guest?" | It makes events of different sizes comparable, so 30 events of different sizes can be learned from together. |
| "Why P85?" | Running short is worse for a hotel than small surplus. P85 means enough food about 85% of the time. It can be changed by the hotel to suit its risk level. |
| "Isn't synthetic data cheating?" | Synthetic data was never used for any reported accuracy number. It was used only for testing code and for a clearly labelled simulation of how accuracy grows with data size. |
| "Why grouped / leave-one-event-out validation?" | The 5 category rows of one event are related. Holding them out together prevents data leakage. |
| "What about events where food ran short?" | Consumption there is underestimated. I flagged them, counted them, and checked results with and without them. |

---

## 10. What I need from you next

1. **Upload the 30 records** (Excel or CSV, any format). I will check the quality, tell you which features are usable, and set up the long-format dataset.
2. Tell me **where the 30 come from** (your hotel only, or mixed) and **whether older records exist at your hotel**.
3. Tell me **what's already written** in the thesis (introduction, literature review?).
4. If your supervisor or university set a **minimum dataset size or required chapters**, tell me so the plan fits that.
