# First Model Results (13 October 2026)

Data: **54 real events** (Aug 2025 to Oct 2026) with booked and actual guest counts.
Test method: **leave-one-event-out**. Each event is predicted by a model trained on the other 53.
Script: `src/attendance_models.py`. Numbers: `results/attendance/results_loeo.csv`. Charts: `results/attendance/fig1_attendance_ratio.png` and `fig2_tradeoff.png`.

---

## 1. The short version

1. **Attendance is close to booked, but it varies.** On average 99% of booked guests came; the middle 80% of events fall between 0.93 and 1.08 of booked. Fewer guests came in 37 events and more came in 11.
2. **The chef's rule (cook for booked) is already a sensible "safe" rule.** It gave enough food in **80% of events** (it ran short in 11 of 54). It behaves like a **P80 safe quantity**, close to the P85 we planned.
3. **The booking details do not predict attendance.** Booked size, day or night, weekend, menu size, month, event type and distance from the client's town are all only weakly related to attendance (correlation at most 0.16). Ridge, random forest, gradient boosting and XGBoost are **no better than a simple average**. This is an honest and normal small-data result.
4. **So the real decision is a trade-off between waste and running short.** Cooking for fewer guests cuts waste but makes food run short more often. The models make this trade-off **visible and measurable**, which the chef's single rule cannot do.

---

## 2. Results table (54 events, leave-one-event-out)

Models use these features: booked guests (log), day/night, weekend, number of dishes, month, wedding or not, and road km from the client's town.
Leftover = (guests cooked for − guests who came) × 0.5 / 0.6 / 0.65 kg by menu size. Cost = LKR 675.40 raw material per plate.

| Method | Avg error (guests) | Leftover kg (95% CI) | Leftover LKR | Ran short (of 54) | Enough food |
|---|---|---|---|---|---|
| **Chef rule: cook for booked** | 11.8 | **248** (178–325) | 272,900 | **11** | 80% |
| Average past ratio (0.99 × booked) | 11.0 | 197 (137–261) | 217,100 | 16 | 70% |
| Median past ratio (0.97 × booked) | 9.8 | 91 (51–138) | 100,400 | 26 | 52% |
| Linear regression | 12.1 | 200 | 220,100 | 20 | 63% |
| Ridge regression | 11.6 | 196 | 216,700 | 19 | 65% |
| Random forest (shallow) | 11.8 | 198 | 218,000 | 18 | 67% |
| Gradient boosting (shallow) | 13.0 | 235 | 258,600 | 20 | 63% |
| XGBoost (shallow) | 12.9 | 226 | 248,800 | 18 | 67% |
| Safe P85: past-ratio percentile | 20.2 | 564 | 621,700 | 9 | 83% |
| **Safe P85: quantile regression** | 15.1 | 398 | 440,400 | **8** | **85%** |
| Safe P85: Ridge + conformal margin | 19.4 | 556 | 612,800 | 8 | 85% |
| Safe P85: quantile GBM | 18.1 | 502 | 554,400 | 10 | 81% |
| Safe P85: XGBoost quantile | 18.4 | 503 | 556,500 | 8 | 85% |

What the table shows:
- **Expected-value models** (average, Ridge, random forest) cut leftover by about **50 kg (about 20%)**, but food runs short more often (16–20 events instead of 11).
- **The median rule** cuts leftover by **63%** (157 kg), but food runs short in about **half** of events.
- **P85 safe models** hit their target (81–85% of events had enough food), but they cook for *more* guests than booked, so leftover rises. **Quantile regression has the best P85 accuracy** (lowest pinball loss: 4.41, against 4.77 for the chef rule).
- **Complex models do not help.** Gradient boosting and XGBoost are the worst expected-value models, and XGBoost quantile (pinball 4.97) is less accurate than plain quantile regression (4.41). That is evidence for choosing simple methods with small data.

---

## 3. The key chart: waste vs running short

`fig2_tradeoff.png` shows every possible safety level, from P40 to P95. Moving left means food runs short less often; moving down means less waste.

- The **chef's rule sits on the curve at about P75–P80**. It is a reasonable choice, but nobody chose it on purpose. It is simply what "cook for booked" happens to give.
- Some example choices the system can offer:

| Safety level | Leftover kg (54 events) | Change vs chef | Events short |
|---|---|---|---|
| P50 (cook for the typical turnout) | 91 | **−63%** | 26 (48%) |
| P65 | 176 | **−29%** | 19 (35%) |
| P70–P75 (same as the chef in practice) | 248 | 0% | 11–14 |
| P85 | 564 | +128% | 9 (17%) |

**Research insight (newsvendor model).** In operations research, the best safety level is shortage cost ÷ (shortage cost + waste cost). The chef's rule gives about 80% coverage. That means the hotel is *implicitly* treating one guest without food as about **4 times as costly** as one wasted plate (0.8 ÷ 0.2 = 4). The system lets management **set that number on purpose**. For example, if a short-food incident costs about 3× a wasted plate, the best level is P75; if it costs 2×, it is P67.

---

## 4. Robustness check: train on the past, test on the future

Trained on the first 32 events (up to 23 July 2026) and tested on the last 22:

| Method | Leftover kg | Events short |
|---|---|---|
| Chef rule | 77 | 6 |
| Average ratio | 41 | 12 |
| Ridge | 48 | 10 |
| P85 quantile regression | 116 | 5 |
| XGBoost | 73 | 10 |

The pattern is the same as in the main results: simple methods cut waste, but food runs short more often, and the safe models cut shortfalls but cost more waste. So the conclusions do not depend on how the data was split.

---

## 5. What this means for the thesis (honest framing)

**Contribution, rewritten to match the evidence:**
1. A data pipeline that turns the hotel's own event-order files into an analysable dataset (69 files → 54 usable events).
2. Evidence that attendance at banquets **cannot be predicted from booking details** in this setting, and that **simple models are as good as ML**. This is an important small-data finding.
3. A **risk-aware decision framework**: a safety-level setting, with quantile regression as the best-calibrated P85 method, that turns attendance uncertainty into a clear waste-versus-shortage choice.
4. Showing that the current chef rule is about a **P80 policy**, and putting numbers on what other policies would save or risk (for example **29% less waste at P65**).

**Limitations to state openly:**
- Leftover is **estimated** with the chef's per-plate rule, not weighed.
- It counts only waste from missing guests, not food left over when everyone came.
- The cost of running short (re-cooking, guest experience) is not measured in LKR.
- It covers one hotel, 54 events, mostly weddings.

---

## 6. Extra feature test: distance from the client's town (14 Oct)

Roshan supplied road km from the hotel to all 24 client towns (0–54 km).

| Distance | Events | Average turnout |
|---|---|---|
| 0–5 km | 13 | 99.7% |
| 5–10 km | 25 | 99.8% |
| 10–20 km | 11 | 98.1% |
| 20–54 km | 5 | 95.3% |

- There is a **small trend**: guests from far towns come a little less. But the correlation is weak (−0.13) and only 5 events are over 20 km.
- Adding distance to the models **changed almost nothing**. The P85 quantile regression improved slightly (pinball loss 4.44 → 4.41, leftover 411 → 398 kg). The expected-value models (Ridge, linear) got slightly worse (Ridge error 11.4 → 11.6 guests). The tables above already include distance. The results without distance are saved in `results/attendance/results_loeo_without_distance.csv`.
- **Conclusion for the thesis:** distance is a sensible feature that deserves more data, but with 54 events it does not make individual events predictable. The main finding stands: the value lies in choosing the safety level, not in predicting each event.
- Rain on the event day could not be tested, because weather data was not reachable from the analysis environment. It goes into future work.

## 7. Earlier options (now done)

The models found no useful features in the booking data. Two quick features *might* predict attendance and are cheap to add (see section 6 for the outcome):
1. **Distance from the client's town to the hotel.** The Location field holds the client's town. Guests travelling far may come less. You can provide km for about 40 towns, or I can estimate it.
2. **Rain on the event day.** Historical weather for Kotadeniyawa can be downloaded for free.

If neither helps, that is still a valid finding: *"attendance uncertainty is mostly random noise, so the value lies in choosing a risk level, not in predicting each event."*
