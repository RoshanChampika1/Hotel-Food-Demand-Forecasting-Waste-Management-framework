# Event-order dataset (built 12 Oct 2026)

Source: 69 RESHEEN event order workbooks (private; kept in `data/raw/`, not in git).
Rebuild: `python src/event_orders/extract_events.py data/raw data/processed` then `python src/event_orders/build_dataset.py data/raw data/processed`. Outputs stay in `data/processed/`, which is git-ignored (real hotel data).

## Files in `data/processed/` (generated locally, not in git)
| File | Rows | What |
|---|---|---|
| `events_clean.csv` | 69 (54 usable) | One row per event. **Use this for modelling.** Filter `usable == 1`. |
| `events_raw.csv` | 69 | Raw fields as read from each file |
| `demand_long.csv` | 7,498 | Chef's planned raw-material demand per event and item |
| `category_demand_long.csv` | 7,498 | Same, with a `category` column (rice_starch, mains, veg_sides, desserts, beverages, other) |
| `menu_long.csv` | 2,924 | Dishes on each event's menu, by menu section |

## Key columns in `events_clean.csv`
- `date`, `month`, `weekday`, `weekend`: taken from the **filename** (2 files had a wrong date inside the sheet)
- `hall`: BH = Banquet Hall, RG = Resheen's Garden (from the filename)
- `session`: day / night (from the filename; the sheet always says "Lunch")
- `event_type`: wedding / homecoming / function / birthday / corporate
- `client_location`: the customer's home town (from the sheet's Location field)
- `road_km`: road distance from the hotel to the client's town, from `data/inputs/town_distance.csv` (supplied by Roshan)
- `rate_lkr`: package price per pax
- `pax_booked`: guest count given by the customer. **The chef cooks for this number.**
- `pax_actual`: guests who actually came (the "Actual Count" note on the menu)
- `attendance_ratio` = pax_actual / pax_booked. **This is the main prediction target.**
- `no_shows`, `extra_guests`
- `kg_per_no_show`: chef's rule by menu size. 0.5 kg for small menus (≤20 dishes), 0.65 kg for bigger or upgraded menus (≥40 dishes or rate above 3,900), 0.6 kg otherwise
- `leftover_est_kg` = no_shows × kg_per_no_show (`_low` and `_high` hold 0.5 and 0.65 for sensitivity)
- `ran_short` = 1 when more guests came than were booked. The chef confirms food runs short for a while and the kitchen cooks again to refill
- `leftover_est_cost_lkr` = no_shows × LKR 675.40 (raw-material cost per plate from the hotel's "75 pax" costing sheet)
- `n_<section>`: number of dishes in each menu section; `n_dishes_total`
- `plan_kg_<category>` and `_per_pax`: chef's planned raw kg for each food category (kg-unit items only)
- `quality_flag`: E = leftover estimated from the chef's rule (attendance itself is recorded)
- `usable`: 1 if booked and actual are both present (54 events). Excluded: 14 files without an actual count, and "Event Order New imo.xlsx", which is a test file (confirmed by Roshan).

## Known limitations
- Leftover is **estimated** from the chef's per-plate rule, not weighed.
- Shortfall is known only as yes/no (more guests than booked). How long it lasted and how much was re-cooked is not recorded.
- `plan_kg_*` counts raw ingredients in kg only. Items in units such as eggs (Ea), noodles (Pkt) and ice cream (4Ltr tubs) are not in the kg totals.
