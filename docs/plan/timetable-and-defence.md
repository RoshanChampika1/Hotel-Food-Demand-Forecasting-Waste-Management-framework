# Timetable, Paper Plan and Viva Defence (11–20 October)

This file replaces the short schedule in section 7 of [rescue-plan-oct20.md](rescue-plan-oct20.md). The methods in that file stay the same.

---

## 1. Honest opinion: is this good enough for a 4th-year CS research project?

**Yes, if you present it correctly.** Here is why, and where the risks are.

### Why it qualifies as Computer Science research
A 4th-year CS project is judged on whether you (a) found a real problem, (b) built and tested a technical solution with a sound method, and (c) can explain and defend it. This project has all three:

| What examiners look for | What you have |
|---|---|
| Real problem | Banquet food waste, with real data from a working hotel |
| Technical contribution | An ML pipeline that gives two outputs: an expected quantity and a **risk-aware safe quantity** (quantile regression + conformal prediction). Conformal prediction is a current ML research topic, not a textbook exercise. |
| Sound evaluation | Leave-one-event-out validation, baselines, confidence intervals, a significance test, and a robustness check |
| Working system | A Streamlit app that a chef could actually use |
| Research finding | How simple versus complex models behave with small data, plus a simulation of how much data is needed |

### Honest risks
1. **Small dataset (30 events, one hotel).** This is the main weakness. You handle it by calling the study a *pilot study*, using methods built for small data, and showing the uncertainty openly. Hiding it is what would fail you; admitting it and handling it well is what passes you.
2. **Supervisor expectations.** Some supervisors expect "big data" or deep learning. **Talk to your supervisor by Tuesday 13 Oct** with the one-page summary (section 6 below). If they accept the pilot framing, you are safe. Do not discover this on the 19th.
3. **Data quality.** If many of the 30 records are estimates (E), results will be weaker. The R-only robustness check covers this.
4. **Time.** 9 days is tight but realistic, because the scaffold already exists. The danger is losing days to collecting more data. **The data freeze is the evening of 14 October, with no exceptions.**

### Realistic grade expectation
- Done as planned, it is a **solid, defensible project**: a clear pass and likely a good grade.
- A top grade needs clean writing, a clear headline result (kg and LKR saved), and a confident viva.
- What would make it fail: claiming more than the data shows, mixing synthetic data into results, or not being able to explain the methods. The plan avoids all three.

### Will it get you "caught" in the situation you fear?
No, as long as you follow one rule: **every number you report comes from your real 30 events, and you say exactly how it was produced.** Being small and honest is acceptable research. Being big and unclear is not.

---

## 2. Excel structure: what I need from it

Upload the **empty template** whenever you can, and the filled data sheet tomorrow morning. I will review the structure as soon as it arrives. For the analysis, the minimum needed per event is:

| Field | Needed? | Notes |
|---|---|---|
| Event ID | Must | Any unique code |
| Date | Must | For weekday/weekend and season |
| Event type | Must | Wedding / corporate / birthday / other |
| Meal time | Must | Lunch / dinner / other |
| Expected guests (booked) | Must | |
| Actual guests (attended) | Must | Needed for per-guest normalisation |
| Prepared kg, for each of the 5 categories | Must | rice/starch, mains, veg/sides, desserts, beverages (beverages may be litres) |
| Leftover kg, for each category | Must | Consumed = prepared − leftover |
| Ran short? (yes/no, per category or per event) | Must | |
| Data quality flag R / M / E | Must | |
| Service style (buffet / plated) | Nice | |
| Number of dishes per category | Nice | Good feature |
| Cost per kg per category | Nice | For the LKR saving; can be filled once from purchase prices |

If some "Must" fields are missing, tell me. Often they can be rebuilt from purchase orders or kitchen sheets.

---

## 3. Writing the thesis and the research paper together

**Strategy: write once, use twice.**
- The **thesis** is the long version. The **paper** is a short version (usually 6 pages in IEEE conference format; check what your university asks for).
- Write each thesis section first. The same evening, spend **30–45 minutes** cutting it down into the matching paper section. Don't write the paper separately at the end.
- Figures and tables are made once and used in both.

| Paper section (~6 pages) | Comes from thesis chapter | Paper length |
|---|---|---|
| Abstract | Written last, from the results | 150–200 words |
| 1. Introduction | Ch 1 Introduction | ~0.75 page |
| 2. Related Work | Ch 2 Literature review | ~0.75 page, 12–20 references |
| 3. Data and Methodology | Ch 3 Methodology | ~1.5 pages |
| 4. System Implementation | Ch 4 System | ~0.5 page, 1 architecture figure |
| 5. Results | Ch 5 Results | ~1.5 pages, 2–3 tables, 2 figures |
| 6. Discussion and Limitations | Ch 6 + 7 | ~0.5 page |
| 7. Conclusion | Ch 8 | ~0.25 page |

---

## 4. Daily timetable

Times are a guide (Sri Lanka time). Adjust them to your hotel work, but keep the **order** and the **end-of-day checkpoints**.

### Day 1 — Sun 11 Oct (tonight)
- Upload the empty Excel template here.
- Send partner-hotel requests: 10 events each, anonymous, 48-hour deadline.
- Make a list of old banquet records available at your hotel.
- Download your university's thesis and paper templates. Note the page limits.
- ✅ Checkpoint: requests sent, templates ready.

### Day 2 — Mon 12 Oct
- **Morning:** upload the 30 records. I check quality and build the clean long-format dataset.
- **Afternoon:** exploratory analysis: per-guest consumption by category and event type, a box plot for each category, counts of R/M/E flags and ran-short events. Choose the final 3–5 features.
- **Evening:** write **Thesis Ch 3 Methodology, part 1** (data collection, the difficulty of getting data, quality flags, per-guest normalisation). Then cut it down into Paper §3, part 1.
- Ongoing: enter any old records from your hotel.
- ✅ Checkpoint: clean dataset, first plots, methodology part 1 drafted.

### Day 3 — Tue 13 Oct
- **Morning:** build the leave-one-event-out evaluation and run the two chef's-rule baselines, Ridge regression and linear quantile regression (P85).
- **Afternoon:** **meet or message your supervisor** with the one-page summary. Get their OK on the pilot framing and on the paper format.
- **Evening:** write **Ch 3 part 2** (models, validation, metrics, synthetic-data rule). Then Paper §3, part 2.
- ✅ Checkpoint: first real results table, supervisor informed.

### Day 4 — Wed 14 Oct — DATA FREEZE
- **Morning:** add the conformal (jackknife+) safe quantity and the shallow random forest and gradient boosting comparisons.
- **Afternoon:** enter the last records. **At 8 pm the dataset is frozen.** Anything that arrives later is only mentioned as future work.
- **Evening:** write **Ch 2 Literature review** (food waste in hospitality, demand forecasting, quantile regression, conformal prediction, learning from small data). Then Paper §2.
- ✅ Checkpoint: data frozen, all models run, literature review drafted.

### Day 5 — Thu 15 Oct
- **Morning:** re-run everything on the frozen data. Add bootstrap 95% confidence intervals and the Wilcoxon test against the baseline.
- **Afternoon:** robustness checks (R-only records, with and without ran-short events). **Waste-saving simulation in kg and LKR. This is the headline result.**
- **Evening:** write **Ch 5 Results, part 1**. Then Paper §5, part 1.
- ✅ Checkpoint: the headline sentence is written ("Over 30 real events, the system would have saved X kg / LKR Y…").

### Day 6 — Fri 16 Oct
- **Morning:** simulation study: learning curve at 30, 60, 100, 200 and 400 synthetic events.
- **Afternoon:** connect the final model to the Streamlit app, take screenshots, draw the architecture diagram.
- **Evening:** write **Ch 5 part 2** (simulation) and **Ch 4 System**. Then Paper §4 and §5, part 2.
- ✅ Checkpoint: all results and the app finished. **Code freeze after today**: bug fixes only from here.

### Day 7 — Sat 17 Oct
- **Morning:** write **Ch 6 Discussion** and **Ch 7 Limitations and future work**.
- **Afternoon:** write **Ch 1 Introduction** (easier now, because you know the results) and **Ch 8 Conclusion**.
- **Evening:** Paper §1, §6 and §7, plus the abstract for both.
- ✅ Checkpoint: **complete first draft of the thesis and the paper.**

### Day 8 — Sun 18 Oct
- **Morning:** read the full thesis once from start to finish and fix logic gaps. Check every number against the results files.
- **Afternoon:** send both drafts to your supervisor (or a friend) for a quick read. Clean up the repo and README.
- **Evening:** start the viva slides (section 5).
- ✅ Checkpoint: drafts sent for feedback, slides started.

### Day 9 — Mon 19 Oct — BUFFER
- **Morning:** apply feedback. Format to the template, check references, number figures and tables.
- **Afternoon:** finish the slides. Do one practice talk out loud, with a timer.
- **Evening:** make the final PDFs. Prepare everything for submission.
- ✅ Checkpoint: final files ready. Nothing new is added today.

### Day 10 — Tue 20 Oct — SUBMIT
- **Submit in the morning.** Keep copies in Google Drive, on a USB stick and in your email.

### If you fall behind, cut in this order
1. The augmentation experiment
2. The random forest and gradient boosting comparison
3. Simulation sizes (use only 30, 100 and 300)
4. App polish

**Never cut:** baselines, Ridge, the P85 safe quantity, leave-one-event-out validation, the kg and LKR waste result, the limitations section.

---

## 5. Viva defence plan

### 5.1 Presentation (about 15 minutes, 12–14 slides)
1. Title
2. The problem: banquet food waste, with a real photo or number from your hotel
3. Why it's hard: you never know exactly how much guests will eat, and running short is worse than having extra
4. Research question and contributions (3 bullets)
5. Data: 30 real events, how they were collected, the R/M/E flags, why hotels don't share data
6. Approach: per-guest normalisation → expected quantity + safe quantity (diagram)
7. Models and why simple models suit small data
8. How it was tested: leave-one-event-out (simple picture)
9. Result 1: accuracy against the chef's rule (table with confidence intervals)
10. Result 2: safe-quantity coverage and shortfall rate
11. **Result 3: waste saved in kg and LKR (the big number)**
12. Simulation: how many events a hotel needs
13. Live demo of the Streamlit app (keep a screenshot slide in case the demo fails)
14. Limitations, future work, conclusion

### 5.2 Demo checklist
- Run the app locally. **Don't depend on the internet.**
- Prepare 2 example events (a wedding dinner for 300 and a corporate lunch for 80) and know their outputs in advance.
- Have a backup screen recording of the demo.

### 5.3 Questions to practise (answer out loud, 30 seconds each)
| Question | Core of your answer |
|---|---|
| Only 30 events. Is that enough? | It's a pilot study. I used methods built for small data and leave-one-out testing, and I report confidence intervals. The simulation shows how results improve with more data. |
| Why not deep learning or XGBoost? | They need hundreds of rows. My shallow tree models already overfit at n=30, which supports this choice. |
| What is conformal prediction, in simple words? | I measure how wrong the model was on each held-out event, and add a margin big enough to cover 85% of those mistakes. That makes the 85% promise rely on real errors, not on assumptions. |
| Why 85%? | Running short is worse than having extra. 85% is a sensible balance, and a hotel can change it to suit its own risk level. |
| Why per guest? | It makes events of different sizes comparable. |
| Is synthetic data cheating? | It was never used for any reported result. It was used only for code testing and a clearly labelled simulation. |
| What about data leakage? | The 5 category rows of one event are always held out together. |
| What about events where food ran short? | Consumption there is underestimated. I flagged those events and checked the results with and without them. |
| How do you know the saving is real? | It is a retrospective simulation on real events. It shows what *would* have happened. A live trial is future work. |
| What would you do with more time? | Collect more events, run a live trial in the kitchen, add partner hotels, and test GBM again once n is in the hundreds. |
| What is the CS contribution? | A risk-aware forecasting pipeline for small data, with an evaluation method and a working tool. |

### 5.4 Things to know cold
- How Ridge regression differs from ordinary linear regression (it adds a penalty that keeps coefficients small).
- What quantile regression minimises (pinball loss, which punishes under-prediction more at q=0.85).
- What MAE, coverage and pinball loss mean.
- What bootstrap confidence intervals and the Wilcoxon test do, in one sentence each.
- Every number on your results slides.

---

## 6. One-page summary for your supervisor (send by Tue 13 Oct)

> **Project update – hotel banquet food demand forecasting**
> Data access from partner hotels was limited, so I am running the study as a **pilot on 30 real banquet events** from my hotel.
> **Research question:** Can a simple, risk-aware forecasting method recommend food quantities that reduce overproduction compared to the chef's current rule, without increasing shortfalls, when only a small number of past events is available?
> **Method:** per-guest consumption for 5 food categories; chef's-rule baselines, Ridge regression, and quantile regression with a conformal safety margin (P85 "safe quantity"); leave-one-event-out validation; bootstrap confidence intervals; a retrospective waste-saving simulation in kg and LKR; and a simulation study on how much data a hotel needs. Synthetic data is used only for that simulation, never for reported results.
> **Output:** a thesis, a research paper, and a working Streamlit tool.
> Could you confirm this framing is acceptable, and the paper format you expect?

---

## 7. What happens next

1. Upload the **empty Excel template** whenever you can. I will check the structure.
2. Upload the **30 filled records tomorrow morning**. I will clean them and start the analysis the same day.
3. Tell me which thesis chapters already exist, if any, and the required paper format.
