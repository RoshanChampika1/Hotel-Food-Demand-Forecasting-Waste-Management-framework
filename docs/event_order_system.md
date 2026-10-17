# Event Order System: design and checks

## What it does
The hotel plans every event in an Excel workbook with three linked parts: the **Party Menu** (dishes),
the **StockBalance** (raw materials) and the **Recipes** book. The app does the same job, and adds
one research step: it decides **how many guests to cook for** instead of always using the booked number.

```
Event details + customer town ─┐
                               ├─> attendance model (quantile regression, safety level P50–P95) ─> guests to cook for
Party Menu (dishes) ───────────┘                                                                      │
                                                                                                      v
                          Recipe book (per 100 guests, or per kg for bites) ──────────────> Stock Balance (Fresh / Dry / Meat)
                                                                                                      │
                                                         Party Menu PDF · Stock Balance PDF · Kitchen recipes PDF · Excel
```

## Where the data comes from
`src/event_system/build_master_data.py` reads every event-order workbook in `data/raw/`:
- **Recipes** come from the recipe sheets ("New Recepies", "Recepies", "RG-Recepies"). The newest workbook's
  version of a recipe is used.
- Each recipe is linked to its menu section through the **hidden matrix in the Party Menu sheet**
  (columns S to PC), which is how the workbook's SUMIFS formulas link them. The matrix also tells the
  basis: normal dishes are per 100 guests; bites are per 1 kg of bite (kg = guests ÷ the chef's divisor,
  for example chicken devilled = guests ÷ 6.81); Ice Coffee is per 100 glasses; Milk Rice is per kg.
- **Items** (code, name, unit, Dry or Fresh) come from the StockBalance sheet. Meat and fish items are
  moved into a separate **Meat** group, so the Stock Balance prints Fresh, then Dry, then Meat.
- **Past menus** (68 events) are kept so staff can start from a previous menu, and dishes are listed
  most-served first.

All of this is hotel data, so `data/master/` and saved orders in `data/orders/` are git-ignored.

## Check against the Excel
`src/event_system/check_against_excel.py` recomputes a past event and compares it with the workbook.
For the 10 Oct 2026 wedding (220 pax), using that workbook's own recipes, **all 122 raw-material
quantities are identical** to the workbook's matrix formulas.

Differences against the printed StockBalance column come from the workbook itself, not the system:
- some StockBalance cells were typed over by hand (for example Baby corn = 1, Ice cream);
- in some newer workbooks the menu moved down one row, so a section falls outside its formula range
  (for example the Action section's Fish cutlets added nothing in the 10 Oct workbook);
- the four dressings are named just "Dressing" in the recipe book, so the workbook never adds them.
  The system keeps the workbook's behaviour here, and lists dishes without a recipe as a warning.

## Guest count
`src/event_system/train_attendance.py` fits quantile regression for P50 to P95 on the real events
(features: booked size, weekend, month, road km from the customer's town) and back-tests each level
with leave-one-event-out. The app shows that back-test next to the chef's rule (cook for booked), so
management can choose the level on purpose. See [results/attendance/RESULTS.md](../results/attendance/RESULTS.md).
