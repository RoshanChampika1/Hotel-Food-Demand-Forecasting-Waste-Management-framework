"""Build the clean event-level dataset from the extracted tables.

Usage: python build_dataset.py <xlsx_folder> <processed_dir>
Reads events_raw.csv and demand_long.csv (from extract_events.py).
Writes events_clean.csv and category_demand_long.csv.
"""
import csv, datetime as dt, os, re, sys

# Chef's rule: each booked guest who does not come leaves 0.5-0.65 kg of food; a bigger menu leaves more.
KG_PER_NO_SHOW_RANGE = (0.5, 0.65)


def kg_per_no_show(n_dishes, rate):
    """Leftover kg per missing guest by menu size (chef: bigger menu -> 0.65 kg)."""
    if n_dishes <= 20:
        return 0.5   # small garden menus (8-12 dishes)
    if n_dishes >= 40 or (rate or 0) > 3900:
        return 0.65  # bigger or upgraded menu
    return 0.6       # standard banquet menu
# Raw-material cost per plate from the hotel's own "75 pax" costing sheet (identical in every file).
# The Price sheet holds purchase totals, not unit prices, so it cannot price individual items.
RAW_COST_PER_PAX_LKR = 675.40

# Raw-material -> food category (first match wins). Items not matched are seasoning/oil/other.
CATEGORY_RULES = [
    ("rice_starch", r"^rice (keeri|white|red|basmathi)|noodles|pasta|spagathi|french fries"),
    ("mains", r"chicken(?!.*(seasoning|powder))|pork|prawn|fish (thalapath|kelawalla|tuna)|cuttle|mutton|beef|cand fish|sausage"),
    ("veg_sides", r"potato|carrot|brinjol|beans green|mushroom|corley|leeks|pumpkin|cabbage|brocali|bell pepper|beet ?root|cucumber"
                  r"|dhal|chick pea|cashew nut|pachoy|lettuce|baby corn|green piees|zucchini|bitter gourd|kidney beans|egg$"),
    ("desserts", r"ice ?cream|jelly|gelatin|water melon|pine apple|grapes|plums|dragon|promagranate|^orange$|apple (green|red)"
                 r"|caned milk|juggery|cooking chocolate|butter cake|curd|icing sugar"),
    ("beverages", r"kanro|nescafe|tea "),
]


def category(item):
    s = item.lower().strip()
    for cat, pat in CATEGORY_RULES:
        if re.search(pat, s):
            return cat
    return "other"


def norm_type(t):
    s = (t or "").lower()
    for key, lab in (("wedding", "wedding"), ("homecoming", "homecoming"), ("birthday", "birthday"),
                     ("copparate", "corporate"), ("corporate", "corporate"), ("function", "function")):
        if key in s:
            return lab
    return "other"


def main(xlsx_dir, proc):
    events = list(csv.DictReader(open(os.path.join(proc, "events_raw.csv"))))
    dist_path = os.path.join(proc, "..", "inputs", "town_distance.csv")
    road_km = {}
    if os.path.exists(dist_path):  # road km from the hotel to the client's town, supplied by Roshan
        road_km = {r["client_location"]: r["road_km_from_hotel"] for r in csv.DictReader(open(dist_path)) if r["road_km_from_hotel"]}
    demand = list(csv.DictReader(open(os.path.join(proc, "demand_long.csv"))))

    agg, cat_rows = {}, []
    for d in demand:
        cat = category(d["item"])
        qty = float(d["demand"])
        cat_rows.append({**d, "category": cat})
        a = agg.setdefault(d["event_id"], {})
        if d["unit"].lower() == "kg" and cat != "other":
            a[f"plan_kg_{cat}"] = a.get(f"plan_kg_{cat}", 0) + qty

    out = []
    for e in events:
        booked = int(float(e["pax_booked"])) if e["pax_booked"] else None
        actual = int(e["pax_actual"]) if e["pax_actual"] else None
        a = agg.get(e["event_id"], {})
        notes = []
        if e["file"] == "Event Order New imo.xlsx":
            notes.append("test file, not a real event (confirmed by Roshan)")
        if not e["date"]:
            notes.append("date missing")
        row = {
            "event_id": e["event_id"], "file": e["file"], "date": e["date"], "hall": e["hall"], "session": e["session"],
            "event_type": norm_type(e["event_type_raw"]), "event_type_raw": e["event_type_raw"],
            "client_location": e["client_location"], "road_km": road_km.get(e["client_location"]), "rate_lkr": e["rate_lkr"],
            "pax_booked": booked, "pax_actual": actual,
        }
        if e["date"]:
            y, m, d = map(int, e["date"].split("-"))
            day = dt.date(y, m, d)
            row.update(month=m, weekday=day.strftime("%a"), weekend=int(day.weekday() >= 5))
        else:
            row.update(month=None, weekday=None, weekend=None)
        for k in sorted(k for k in e if k.startswith("n_")):
            row[k] = e[k]
        row["n_dishes_total"] = sum(int(e[k]) for k in e if k.startswith("n_") and k not in ("n_dressing", "n_condiments"))
        for cat in ("rice_starch", "mains", "veg_sides", "desserts"):
            row[f"plan_kg_{cat}"] = round(a.get(f"plan_kg_{cat}", 0), 2)
            row[f"plan_kg_{cat}_per_pax"] = round(a.get(f"plan_kg_{cat}", 0) / booked, 4) if booked else None
        if booked and actual:
            gap = booked - actual
            row["attendance_ratio"] = round(actual / booked, 4)
            row["no_shows"] = max(gap, 0)
            row["extra_guests"] = max(-gap, 0)
            per_plate = kg_per_no_show(row["n_dishes_total"], float(e["rate_lkr"] or 0))
            row["kg_per_no_show"] = per_plate
            row["leftover_est_kg"] = round(max(gap, 0) * per_plate, 1)
            row["leftover_est_kg_low"] = round(max(gap, 0) * KG_PER_NO_SHOW_RANGE[0], 1)
            row["leftover_est_kg_high"] = round(max(gap, 0) * KG_PER_NO_SHOW_RANGE[1], 1)
            row["leftover_est_cost_lkr"] = round(max(gap, 0) * RAW_COST_PER_PAX_LKR, 0)
            # More guests than booked: food ran short for a while and the kitchen cooked again to refill (chef)
            row["ran_short"] = int(gap < 0)
            row["quality_flag"] = "E"  # leftover estimated from chef's per-plate rule; attendance itself is recorded
        else:
            row.update(attendance_ratio=None, no_shows=None, extra_guests=None, leftover_est_kg=None,
                       leftover_est_kg_low=None, leftover_est_kg_high=None, leftover_est_cost_lkr=None, kg_per_no_show=None,
                       ran_short=None, quality_flag="")
            notes.append("actual count missing")
        row["usable"] = int(bool(booked and actual and e["file"] != "Event Order New imo.xlsx"))
        row["notes"] = "; ".join(notes)
        out.append(row)

    for fname, rows in (("events_clean.csv", out), ("category_demand_long.csv", cat_rows)):
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with open(os.path.join(proc, fname), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        print(fname, len(rows))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
