"""RESHEEN Hotel & Banquets - Event Order System.

Plan an event the way the hotel's Excel event order does it (Party Menu -> StockBalance -> Recipes),
with one addition from the research: the number of guests to cook for comes from the attendance
model at a chosen safety level, instead of always cooking for the booked number.

One page of the app (app/streamlit_app.py runs it). Run:  streamlit run app/streamlit_app.py
"""
import json
import sys
from datetime import date, datetime, time
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "event_system"))
sys.path.insert(0, str(ROOT / "app"))
import exports  # noqa: E402
from ui import hero, kpi  # noqa: E402
from order_calc import (SECTIONS, SECTION_TITLE, STOCK_GROUPS, RAW_COST_PER_PAX, backtest,  # noqa: E402
                        bite_divisor, dish_options, event_demand, load_master, load_model, load_towns,
                        safe_guests)

ORDERS = ROOT / "data" / "orders"
EVENT_TYPES = ["Wedding", "Homecoming", "Birthday Party", "Function", "Corporate", "Engagement", "Other"]
HALLS = {"Banquet Hall (BH)": "Banquet Hall", "R Garden (RG)": "R Garden"}


@st.cache_data(show_spinner="Loading recipes and menus...")
def get_master():
    return load_master()


@st.cache_data
def get_model():
    return load_model()


hero("🍽️ RESHEEN Hotel &amp; Banquets",
     "Event Order System &nbsp;·&nbsp; Party Menu → Guest forecast → Stock Balance → Kitchen")

try:
    master = get_master()
except FileNotFoundError as e:
    st.error(str(e))
    st.info("Put the event-order Excel files in data/raw/ first, then run the command above (about 5 minutes).")
    st.stop()
model = get_model()
towns = load_towns()
ss = st.session_state


# ------------------------------------------------------------------ helpers for menus
def section_options(sec):
    opts = dish_options(master, sec) + ss.get(f"extra_{sec}", [])
    chosen = ss.get(f"ms_{sec}", [])
    return list(dict.fromkeys(opts + chosen))


def load_past_menu():
    label = ss.get("past_menu")
    if not label or label == "-":
        return
    m = next(p for p in master["past_menus"] if past_label(p) == label)
    for sec, _ in SECTIONS:
        allowed = set(section_options(sec))
        ss[f"ms_{sec}"] = [d for d in m["sections"].get(sec, []) if d in allowed]


def past_label(p):
    return f'{p["date"]} · {p["hall"]} {p["session"]} · {p.get("event_type", "")} · {p.get("pax", "")} pax'


def load_saved_order():
    name = ss.get("saved_order")
    if not name or name == "-":
        return
    o = json.loads((ORDERS / name).read_text())
    for sec, _ in SECTIONS:
        ss[f"ms_{sec}"] = o["menu"].get(sec, [])
    for k in ("booked", "event_no", "hall_label", "session", "event_type", "location", "road_km", "level"):
        if k in o["event"]:
            ss[f"ev_{k}"] = o["event"][k]
    ss["ev_date"] = date.fromisoformat(o["event"]["date"])
    ss["ev_time"] = time.fromisoformat(o["event"]["serving_time_24"])


# ------------------------------------------------------------------ sidebar: event details
with st.sidebar:
    st.markdown("### 🗓️ Event details")
    ev_date = st.date_input("Date of event", key="ev_date", value=date.today())
    session = st.radio("Session", ["Day", "Night"], key="ev_session", horizontal=True)
    hall_label = st.radio("Hall", list(HALLS), key="ev_hall_label", horizontal=True)
    event_type = st.selectbox("Type of event", EVENT_TYPES, key="ev_event_type")
    event_no = st.text_input("Event No", key="ev_event_no", value="LR024-")
    default_time = time(12, 30) if session == "Day" else time(20, 30)
    serving = st.time_input("Food serving time", key="ev_time", value=default_time, step=900)
    booked = st.number_input("No of Pax (booked by customer)", 10, 2000, 200, 5, key="ev_booked")

    st.markdown("### 📍 Customer location")
    town_list = sorted(towns) + ["Other town..."]
    location = st.selectbox("Town the guests come from", town_list,
                            index=town_list.index("Kotadeniyawa") if "Kotadeniyawa" in town_list else 0,
                            key="ev_location")
    if location == "Other town...":
        location = st.text_input("Town name", key="ev_other_town") or "Other"
        road_km = st.number_input("Road distance from hotel (km)", 0.0, 300.0, 10.0, 0.5, key="ev_road_km")
    else:
        road_km = float(towns[location])
        st.caption(f"Road distance from hotel: **{road_km:g} km**")

    st.markdown("### 🛡️ Safety level")
    level = st.select_slider(
        "How sure should we be that food is enough?",
        options=[0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95], value=0.80,
        format_func=lambda q: f"P{int(q * 100)}", key="ev_level")
    st.caption("P80 = enough food at about 8 of 10 events. Higher = fewer shortfalls but more leftover.")

guests, ratio = safe_guests(model, booked, ev_date, road_km, level)
expected, exp_ratio = safe_guests(model, booked, ev_date, road_km, 0.50)
override = ss.get("override_on") and ss.get("override_val")
if override:
    guests = int(ss["override_val"])

hall = HALLS[hall_label]
ev = dict(date=ev_date, session=session.lower(), hall=hall, event_type=event_type, event_no=event_no,
          serving_time=serving.strftime("%I.%M %p").lstrip("0"), location=location, road_km=road_km,
          booked=booked, guests=guests, level=level)

# ------------------------------------------------------------------ KPI row
k1, k2, k3, k4 = st.columns(4)
kpi(k1, "Booked pax", f"{booked}", f"{event_type} · {session} · {hall}")
kpi(k2, "Expected to come", f"{expected}", f"typical turnout {exp_ratio:.0%} of booked")
kpi(k3, "Cook for", f"{guests}", "manual override" if override else f"safe level P{int(level * 100)}")
diff = guests - booked
kpi(k4, "vs booked", f"{diff:+d}", f"≈ {abs(diff) * 0.6:.0f} kg food {'less' if diff < 0 else 'more'} than "
                                   "cooking for booked" if diff else "same as booked")
st.write("")

tab_menu, tab_fc, tab_sb, tab_rec, tab_print = st.tabs(
    ["🍽️ Party Menu", "👥 Guest forecast", "📦 Stock Balance", "👨‍🍳 Kitchen recipes", "🖨️ Print & save"])

# ------------------------------------------------------------------ 1. Party Menu
with tab_menu:
    a, b = st.columns([3, 2])
    pm = sorted(master["past_menus"], key=lambda p: p["date"], reverse=True)
    a.selectbox("Start from a past event's menu (optional)", ["-"] + [past_label(p) for p in pm],
                key="past_menu", on_change=load_past_menu)
    saved = sorted(p.name for p in ORDERS.glob("*.json")) if ORDERS.exists() else []
    b.selectbox("Open a saved order", ["-"] + saved, key="saved_order", on_change=load_saved_order)

    menu = {}
    left, right = st.columns(2)
    half = len(SECTIONS) // 2 + 1
    for i, (sec, title) in enumerate(SECTIONS):
        opts = section_options(sec)
        if not opts and sec in ("mutton", "beef"):
            continue
        with (left if i < half else right):
            st.markdown(f'<div class="sec">{title}</div>', unsafe_allow_html=True)
            menu[sec] = st.multiselect(title, opts, key=f"ms_{sec}", label_visibility="collapsed",
                                       placeholder="Choose dishes (most served first)")

    with st.expander("➕ Add a dish that is not in the list"):
        c1, c2, c3 = st.columns([2, 3, 1])
        new_sec = c1.selectbox("Section", [s for s, _ in SECTIONS], format_func=SECTION_TITLE.get, key="new_sec")
        new_dish = c2.text_input("Dish name", key="new_dish")
        if c3.button("Add", width="stretch") and new_dish.strip():
            ss.setdefault(f"extra_{new_sec}", []).append(new_dish.strip())
            ss[f"ms_{new_sec}"] = ss.get(f"ms_{new_sec}", []) + [new_dish.strip()]
            st.rerun()
        st.caption("A new dish prints on the menu. It adds raw materials only after its recipe is added "
                   "to the recipe book (Excel) and the master data is rebuilt.")

    # bites in kg and counted items
    bite_kg, counts = {}, {}
    if menu.get("bites"):
        st.markdown('<div class="sec">BITES - quantity (kg = guests ÷ divisor, as in the Excel)</div>',
                    unsafe_allow_html=True)
        bt = pd.DataFrame({"Bite": menu["bites"],
                           "Divisor": [bite_divisor(master, d) for d in menu["bites"]],
                           "Fixed kg (optional)": [None] * len(menu["bites"])})
        bt = st.data_editor(bt, hide_index=True, width="stretch", key=f"bites_{'|'.join(menu['bites'])}",
                            disabled=["Bite"],
                            column_config={"Divisor": st.column_config.NumberColumn(min_value=1.0, step=0.01, format="%.2f"),
                                           "Fixed kg (optional)": st.column_config.NumberColumn(min_value=0.0)})
        for r in bt.itertuples():
            fixed = r[3]
            bite_kg[r.Bite] = float(fixed) if pd.notna(fixed) and fixed else guests / float(r.Divisor)
        st.caption(" · ".join(f"**{d}** {k:.2f} kg" for d, k in bite_kg.items()))

    counted = [d for s in ("welcome", "soup", "special") for d in menu.get(s, [])]
    if counted:
        st.markdown('<div class="sec">GLASSES / BOWLS / KG to prepare</div>', unsafe_allow_html=True)
        d = master["dishes"].set_index("dish")
        cols = st.columns(min(4, len(counted)))
        for i, dsh in enumerate(counted):
            basis = d.basis.get(dsh, "per_100_pax") if dsh in d.index else "per_100_pax"
            basis = basis if isinstance(basis, str) else basis.iloc[0]
            default = 10 if basis == "per_unit_count" else guests
            unit = "kg" if basis == "per_unit_count" else "glasses / bowls"
            counts[dsh] = cols[i % len(cols)].number_input(f"{dsh} ({unit})", 0, 5000, int(default), key=f"cnt_{dsh}")

lines, sb, missing = event_demand(master, menu, guests, bite_kg, counts)
n_dishes = sum(len(v) for v in menu.values())

# ------------------------------------------------------------------ 2. Guest forecast
with tab_fc:
    st.markdown("#### How many guests should the kitchen cook for?")
    c1, c2 = st.columns([3, 2])
    with c1:
        if model is None:
            st.warning("Attendance model not found. Run `python src/event_system/train_attendance.py`. "
                       "Until then the system cooks for the booked number.")
        st.markdown(
            f"""<div class="note">The customer booked <b>{booked}</b> guests. From the hotel's past
            {model['n_events'] if model else 0} events with an actual head count, the model expects about
            <b>{expected}</b> to come (P50). To have enough food at about <b>{int(level * 100)} of 100</b>
            events like this one, cook for <b>{guests}</b> guests.<br>
            The model uses booked size, weekend or weekday, month and road distance from <b>{location}</b>
            ({road_km:g} km). Quantile regression was the most accurate safe method in the research.</div>""",
            unsafe_allow_html=True)
        st.write("")
        st.checkbox("Manager override: set the number to cook for myself", key="override_on")
        if ss.get("override_on"):
            st.number_input("Guests to cook for", 1, 3000, int(guests), key="override_val")
    with c2:
        if model:
            rows = [dict(Level="Chef rule (cook for booked)", **{"Leftover kg": model["chef_rule"]["leftover_kg"],
                                                                 "Food ran short": model["chef_rule"]["short_events"]})]
            for q, bt_ in model["backtest"].items():
                rows.append({"Level": f"P{int(float(q) * 100)}", "Leftover kg": bt_["leftover_kg"],
                             "Food ran short": bt_["short_events"]})
            tb = pd.DataFrame(rows)
            st.markdown(f"**What each level would have done on the past {model['n_events']} events**")
            st.dataframe(tb.style.apply(lambda r: ["background-color:#f2e6d0" if r.Level == f"P{int(level*100)}"
                                                   else "" for _ in r], axis=1)
                         .format({"Leftover kg": "{:.0f}"}),
                         hide_index=True, width="stretch", height=420)
            st.caption("Leave-one-event-out test. Leftover is estimated with the chef's rule "
                       "(0.5 to 0.65 kg per missing guest).")
    if model:
        bt_ = backtest(model, level)
        chart = tb[tb.Level.str.startswith("P")].copy()
        chart["Level"] = chart.Level.str[1:].astype(int)
        st.markdown("**Waste versus running short**")
        st.line_chart(chart.set_index("Level")[["Leftover kg"]], height=220, color="#7a1f2b")
        st.line_chart(chart.set_index("Level")[["Food ran short"]], height=180, color="#c9a24a")

# ------------------------------------------------------------------ 3. Stock Balance
with tab_sb:
    if sb.empty:
        st.info("Choose dishes in the Party Menu tab to see the Stock Balance.")
    else:
        g1, g2, g3, g4 = st.columns(4)
        kpi(g1, "Items to issue", len(sb), f"for {guests} guests")
        for col, g in zip((g2, g3, g4), STOCK_GROUPS):
            part = sb[sb.group == g]
            kpi(col, f"{g} items", len(part), f"{part[part.unit.str.lower().isin(['kg'])].demand.sum():.1f} kg by weight")
        if missing:
            st.warning("No recipe in the recipe book for: " + ", ".join(missing) +
                       ". They print on the menu but add no raw materials.")
        for g in STOCK_GROUPS:
            part = sb[sb.group == g]
            if part.empty:
                continue
            st.markdown(f'<div class="grp">{g} items ({len(part)})</div>', unsafe_allow_html=True)
            st.dataframe(
                part[["item_code", "description", "unit", "demand", "issue", "used_in"]].rename(columns={
                    "item_code": "Item Code", "description": "Description", "unit": "Unit", "demand": "Demand",
                    "issue": "Issue", "used_in": "Used in"}),
                hide_index=True, width="stretch",
                column_config={"Demand": st.column_config.NumberColumn(format="%.3f"),
                               "Issue": st.column_config.NumberColumn(format="%.2f")})
        if guests != booked:
            st.caption(f"Quantities are for {guests} guests. Cooking for the booked {booked} would need "
                       f"{booked / guests:.1%} of these amounts.")

# ------------------------------------------------------------------ 4. Kitchen recipes
with tab_rec:
    if lines.empty:
        st.info("Choose dishes in the Party Menu tab.")
    else:
        st.caption(f"Ingredient quantities for each dish, for {guests} guests (from the hotel recipe book).")
        for (sec, dsh), part in lines.groupby(["menu_section", "dish"], sort=False):
            with st.expander(f"{SECTION_TITLE.get(sec, sec)}  ·  {dsh}  ·  {len(part)} ingredients"):
                st.dataframe(part[["item_code", "item_name", "unit", "demand", "qty", "recipe_unit"]].rename(
                    columns={"item_code": "Code", "item_name": "Ingredient", "unit": "Unit", "demand": "Qty",
                             "qty": "Recipe qty", "recipe_unit": "Recipe unit"}),
                    hide_index=True, width="stretch",
                    column_config={"Qty": st.column_config.NumberColumn(format="%.3f")})
                st.caption(f"Basis: {part.how.iloc[0]}")

# ------------------------------------------------------------------ 5. Print and save
with tab_print:
    if n_dishes == 0:
        st.info("Choose dishes in the Party Menu tab first.")
    else:
        stem = f"{ev_date:%Y-%m-%d}_{hall.replace(' ', '')}_{session}"
        st.markdown("#### Print for the kitchen")
        c1, c2, c3, c4 = st.columns(4)
        c1.download_button("📋 Party Menu (PDF)",
                           exports.party_menu_pdf(ev, menu, bite_kg, counts),
                           f"PartyMenu_{stem}.pdf", "application/pdf", width="stretch")
        if not sb.empty:
            c2.download_button("📦 Stock Balance (PDF)",
                               exports.stock_balance_pdf(ev, sb, bite_kg),
                               f"StockBalance_{stem}.pdf", "application/pdf", width="stretch")
            c3.download_button("👨‍🍳 Kitchen recipes (PDF)", exports.recipes_pdf(ev, lines),
                               f"KitchenRecipes_{stem}.pdf", "application/pdf", width="stretch")
        c4.download_button("📗 All sheets (Excel)", exports.to_excel(ev, menu, bite_kg, counts, sb, lines),
                           f"EventOrder_{stem}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           width="stretch")
        st.caption("The Party Menu and Stock Balance are separate files, so the menu can go on the kitchen "
                   "notice board and the Stock Balance to the chef.")

        st.markdown("#### Save this order")
        if st.button("💾 Save order", type="primary"):
            ORDERS.mkdir(parents=True, exist_ok=True)
            data = dict(saved_at=datetime.now().isoformat(timespec="seconds"),
                        event=dict(date=ev_date.isoformat(), session=session, hall_label=hall_label,
                                   event_type=event_type, event_no=event_no, location=ss.get("ev_location"),
                                   road_km=road_km, booked=booked, level=level, guests=guests,
                                   serving_time_24=serving.strftime("%H:%M")),
                        menu=menu, bite_kg=bite_kg, counts=counts)
            (ORDERS / f"{stem}.json").write_text(json.dumps(data, indent=1))
            st.success(f"Saved as data/orders/{stem}.json. After the event, write the actual guest count "
                       "in the Excel as before, so the model can learn from it.")

        est = max(0, guests - expected) * 0.6
        st.markdown(f"""<div class="note"><b>Estimated raw-material cost</b> for {guests} plates:
        LKR {guests * RAW_COST_PER_PAX:,.0f} (LKR {RAW_COST_PER_PAX:,.2f} per plate, hotel costing sheet).
        Expected leftover if the typical {expected} guests come: about {est:.0f} kg.</div>""",
                    unsafe_allow_html=True)
