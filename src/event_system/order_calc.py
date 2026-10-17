"""Core logic of the event-order system: master data, safe guest count and the StockBalance demand.

The demand follows the hotel's own workbook formulas:
  normal dish   : recipe qty is for 100 guests  -> qty / 100 * guests
  bite          : recipe qty is for 1 kg of bite -> qty * bite kg   (bite kg = guests / chef's divisor)
  counted item  : Ice Coffee etc. per 100 glasses -> qty / 100 * glasses; Milk rice per kg -> qty * kg
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "data" / "master"
MODEL = ROOT / "models" / "attendance_quantreg.json"
TOWNS = ROOT / "data" / "inputs" / "town_distance.csv"

# Order of sections on the printed Party Menu, with the kitchen's headings
SECTIONS = [
    ("welcome", "WELCOME DRINK"), ("bites", "BITES"), ("special", "SPECIAL"), ("salad", "SALAD"),
    ("dressing", "DRESSING"), ("soup", "SOUP"), ("hot_chaffer", "HOT CHAFFER"), ("chicken", "CHICKEN"),
    ("pork", "PORK"), ("fish", "SHELL FISH / FISH"), ("mutton", "MUTTON"), ("beef", "BEEF"),
    ("vegetable", "VEGETABLE"), ("action", "ACTION"), ("condiments", "CONDIMENTS"), ("desserts", "DESSERTS"),
]
SECTION_TITLE = dict(SECTIONS)
STOCK_GROUPS = ["Fresh", "Dry", "Meat"]          # StockBalance order asked for by the hotel
COUNT_UNITS = {"pkt", "bot", "ea", "nos", "pcs", "tin", "can", "roll", "box"}
RAW_COST_PER_PAX = 675.40


# ---------------------------------------------------------------- master data
def load_master(master_dir=MASTER):
    master_dir = Path(master_dir)
    if not (master_dir / "recipes.csv").exists():
        raise FileNotFoundError(
            f"No master data in {master_dir}. Run: python src/event_system/build_master_data.py data/raw data/master")
    m = dict(
        items=pd.read_csv(master_dir / "items.csv"),
        recipes=pd.read_csv(master_dir / "recipes.csv"),
        dishes=pd.read_csv(master_dir / "dishes.csv"),
        bites=pd.read_csv(master_dir / "bites.csv"),
    )
    m["past_menus"] = json.loads((master_dir / "past_menus.json").read_text())
    return m


def dish_options(master, section):
    d = master["dishes"]
    d = d[(d.section == section) & ((d.has_recipe == 1) | (d.times_served >= 2))]  # drop one-off notes like "Tea"
    d = d.sort_values(["times_served", "dish"], ascending=[False, True])
    return d.dish.drop_duplicates().tolist()


def bite_divisor(master, dish, default=15.0):
    b = master["bites"]
    hit = b[b.dish_key == dish.strip().lower()]
    return float(hit.divisor.iloc[0]) if len(hit) else default


def load_towns(path=TOWNS):
    if Path(path).exists():
        t = pd.read_csv(path)
        return dict(zip(t.client_location, t.road_km_from_hotel))
    return {}


# ---------------------------------------------------------------- attendance model
def load_model(path=MODEL):
    return json.loads(Path(path).read_text()) if Path(path).exists() else None


def safe_guests(model, booked, date, road_km, level):
    """Return (guests to cook for, predicted attendance ratio) at the chosen safety level."""
    if model is None:
        return booked, 1.0
    month = date.month
    x = dict(log_booked=np.log(max(booked, 1)), weekend=int(date.weekday() >= 5),
             month_sin=np.sin(2 * np.pi * month / 12), month_cos=np.cos(2 * np.pi * month / 12),
             road_km=float(road_km))
    z = np.array([1.0] + [(x[f] - mu) / sd for f, mu, sd in zip(model["features"], model["mean"], model["std"])])
    ratios = {float(q): float(z @ np.array(p)) for q, p in model["levels"].items()}
    # quantile lines can cross at small n: keep them in order
    qs = sorted(ratios)
    mono = np.maximum.accumulate([ratios[q] for q in qs])
    ratio = float(np.interp(level, qs, mono))
    return int(math.ceil(ratio * booked)), ratio


def backtest(model, level):
    if model is None:
        return None
    return model["backtest"].get(f"{level:.2f}")


# ---------------------------------------------------------------- demand
def dish_lines(master, section, dish, guests, bite_kg=None, count=None):
    """Raw-material lines for one dish at this event's size."""
    r = master["recipes"]
    key = dish.strip().lower().replace("’", "'")
    rk = r.dish_key.str.replace("’", "'")
    lines = r[(rk == key) & (r.section == section)]
    if lines.empty:
        lines = r[rk == key]  # recipe kept under another section
        if not lines.empty:
            lines = lines[lines.section == lines.section.iloc[0]]
    if lines.empty:
        return pd.DataFrame()
    lines = lines.copy()
    basis = lines.basis.iloc[0]
    if basis == "per_kg_bite":
        factor, how = (bite_kg or 0), f"per kg × {bite_kg or 0:.2f} kg"
    elif basis in ("per_100_count", "per_100_count_bite"):
        n = count if count else guests
        factor, how = n / 100, f"per 100 × {n}"
    elif basis == "per_unit_count":
        n = count if count else 0
        factor, how = n, f"per unit × {n}"
    else:
        factor, how = guests / 100, f"per 100 pax × {guests}"
    lines["demand"] = lines.qty * factor
    lines["dish"], lines["menu_section"], lines["how"] = dish, section, how
    return lines


def event_demand(master, menu, guests, bite_kg, counts):
    """menu: {section: [dishes]}. Returns (item lines per dish, StockBalance per item, dishes without recipe)."""
    parts, missing = [], []
    for sec, dishes in menu.items():
        for dsh in dishes:
            ln = dish_lines(master, sec, dsh, guests, bite_kg.get(dsh), counts.get(dsh))
            if ln.empty:
                missing.append(dsh)
            else:
                parts.append(ln)
    if not parts:
        return pd.DataFrame(), pd.DataFrame(), missing
    lines = pd.concat(parts, ignore_index=True)
    items = master["items"].drop_duplicates("item_key").set_index("item_key")
    lines["group"] = lines.item_key.map(items.group).fillna("Dry")
    lines["unit"] = lines.item_key.map(items.unit).fillna(lines.recipe_unit).fillna("Kg")
    lines["stock_name"] = lines.item_key.map(items.item_name).fillna(lines.item_name)
    lines["order"] = lines.item_key.map(items["order"]).fillna(9999)
    sb = (lines.groupby(["group", "item_key"], as_index=False)
          .agg(item_code=("item_code", "first"), description=("stock_name", "first"), unit=("unit", "first"),
               demand=("demand", "sum"), order=("order", "first"),
               used_in=("dish", lambda s: ", ".join(sorted(set(s))))))
    sb["issue"] = [issue_qty(q, u) for q, u in zip(sb.demand, sb.unit)]
    sb["group"] = pd.Categorical(sb.group, STOCK_GROUPS, ordered=True)
    sb = sb.sort_values(["group", "order", "description"]).reset_index(drop=True)
    return lines, sb, missing


def issue_qty(q, unit):
    """Round the demand to what the store can issue: whole packets/bottles, 0.05 kg otherwise."""
    if str(unit).strip().lower() in COUNT_UNITS:
        return float(math.ceil(q - 1e-9))
    return round(math.ceil(q * 20 - 1e-9) / 20, 2)
