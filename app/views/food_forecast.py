"""Food Forecast page: expected and safe (P85) quantity per food category.

Three tabs:
  One event          fill in a short form
  Upload a list      CSV or Excel with many events, checked row by row before forecasting
  Analysis & export  totals, charts and an Excel / CSV download of the uploaded list's forecast
Models: linear regression (expected) and quantile GBM at P85 (safe), trained by src/train.py.
"""
import io
import sys
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))
from predict import CATEGORIES, predict_batch  # noqa: E402
from ui import hero, kpi, kpi_row, step  # noqa: E402
from upload_validation import (MAX_ROWS, SUPPORTED_EVENT_TYPES, SUPPORTED_MEAL_TYPES, UploadError,  # noqa: E402
                               read_upload, template_csv, validate_upload)

LABEL = {"rice_starch": "Rice & starch", "mains": "Mains", "veg_sides": "Vegetables & sides",
         "desserts": "Desserts", "beverages": "Beverages"}
UNIT = {c: ("L" if c == "beverages" else "kg") for c in CATEGORIES}
COLORS = ["#c9a24a", "#7a1f2b"]          # expected, safe
ss = st.session_state

hero("📊 Food Forecast",
     "How much of each food to prepare: the <b>expected</b> amount, and a <b>safe</b> amount "
     "that is enough at about 85 of 100 events")


def run_forecast(events):
    try:
        return predict_batch(events)
    except FileNotFoundError as e:
        st.error(f"The food models are not trained yet. {e}")
        st.stop()


def category_table(pred):
    """Totals per category: expected, safe and the extra the safe amount adds."""
    rows = []
    for c in CATEGORIES:
        exp, safe = pred[f"{c}_expected"].sum(), pred[f"{c}_safe"].sum()
        rows.append({"Food": LABEL[c], "Unit": UNIT[c], "Expected": exp, "Safe (P85)": safe,
                     "Extra for safety": safe - exp})
    return pd.DataFrame(rows)


def bar_chart(table):
    long = table.melt(id_vars="Food", value_vars=["Expected", "Safe (P85)"], var_name="Amount", value_name="kg / L")
    chart = alt.Chart(long).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("Food:N", sort=[LABEL[c] for c in CATEGORIES], title=None),
        yOffset="Amount:N", x=alt.X("kg / L:Q"),
        color=alt.Color("Amount:N", scale=alt.Scale(range=COLORS), legend=alt.Legend(orient="bottom", title=None)),
        tooltip=["Food", "Amount", alt.Tooltip("kg / L:Q", format=".1f")])
    st.altair_chart(chart.properties(height=300), width="stretch")


tab_one, tab_up, tab_an = st.tabs(["✏️ One event", "📤 Upload a list", "📈 Analysis & export"])

# ------------------------------------------------------------------ 1. one event
with tab_one:
    with st.form("one_event"):
        c1, c2, c3, c4 = st.columns(4)
        ev_date = c1.date_input("Event date", value=date.today())
        ev_type = c2.selectbox("Event type", SUPPORTED_EVENT_TYPES, format_func=str.title,
                               help="Homecoming, engagement and function count as Other.")
        meal = c3.selectbox("Meal", SUPPORTED_MEAL_TYPES, format_func=str.title,
                            help="Lunch = day event, Dinner = night event.")
        guests = c4.number_input("Booked guests", 1, 5000, 200, 5)
        go = st.form_submit_button("Forecast", type="primary")

    if go or "fc_one" in ss:
        if go:
            ev = pd.DataFrame([{"event_date": ev_date.isoformat(), "event_type": ev_type, "meal_type": meal,
                                "guests_expected": int(guests)}])
            ss["fc_one"] = (ev, run_forecast(ev))
        ev, pred = ss["fc_one"]
        e = ev.iloc[0]
        st.caption(f"Forecast for a **{e.event_type}** {e.meal_type} on **{e.event_date}** "
                   f"with **{e.guests_expected}** booked guests.")
        kpi_row([(LABEL[c], f"{pred[f'{c}_safe'].iloc[0]:.1f} {UNIT[c]}",
                  f"safe · expected {pred[f'{c}_expected'].iloc[0]:.1f}") for c in CATEGORIES])
        st.write("")
        table = category_table(pred)
        left, right = st.columns([3, 2])
        with left:
            bar_chart(table)
        with right:
            st.dataframe(table, hide_index=True, width="stretch",
                         column_config={k: st.column_config.NumberColumn(format="%.1f")
                                        for k in ("Expected", "Safe (P85)", "Extra for safety")})
            st.download_button("⬇️ Download this forecast (CSV)", table.to_csv(index=False).encode(),
                               f"food_forecast_{e.event_date}.csv", "text/csv")
        st.caption("Prepare the **safe** amount when running short is worse than a little leftover. "
                   "Amounts are prepared kg (raw ingredients), beverages in litres.")

# ------------------------------------------------------------------ 2. upload
with tab_up:
    step(1, "Download the template and fill in one row per event")
    st.download_button("⬇️ Template (CSV)", template_csv(), "food_forecast_template.csv", "text/csv")
    st.caption("Columns: **event_id** (optional), **event_date** (YYYY-MM-DD or DD/MM/YYYY), "
               "**event_type** (wedding, corporate, birthday, other), **meal_type** (lunch/day or dinner/night), "
               f"**guests_expected** (booked guests, 1–5000). Up to {MAX_ROWS} events per file.")

    step(2, "Upload the file")
    up = st.file_uploader("CSV or Excel (.xlsx), up to 5 MB", type=["csv", "xlsx"], key="fc_file")

    if up is not None:
        step(3, "Check the result")
        try:
            result = validate_upload(read_upload(up.name, up.getvalue()))
        except UploadError as e:
            result = None
            st.error(str(e))
    if up is not None and result is not None:
        n_ok, n_bad = len(result.valid), result.n_error_rows
        a, b, c = st.columns(3)
        kpi(a, "Events ready", n_ok, "will be forecast")
        kpi(b, "Rows with problems", n_bad, "skipped, see below" if n_bad else "none", tone="gold")
        kpi(c, "File", up.name, f"{len(up.getvalue()) / 1024:.0f} KB")
        st.write("")
        for w in result.warnings:
            st.info(w)
        if len(result.errors):
            st.warning("Fix these rows in your file and upload it again. Row numbers are as Excel shows them.")
            st.dataframe(result.errors.rename(columns=str.title), hide_index=True, width="stretch")
            st.download_button("⬇️ Problem list (CSV)", result.errors.to_csv(index=False).encode(),
                               "upload_problems.csv", "text/csv")
        if n_ok:
            pred = run_forecast(result.valid)
            ss["fc_batch"] = (result.valid, pred, result.errors, up.name)
            st.success(f"{n_ok} event(s) forecast. Open the **Analysis & export** tab for totals, charts and downloads.")
            preview = result.valid.drop(columns="row").join(
                pred[[f"{c}_safe" for c in CATEGORIES]].rename(columns=lambda k: f"{LABEL[k[:-5]]} (safe)"))
            st.dataframe(preview.head(50), hide_index=True, width="stretch")
            if n_ok > 50:
                st.caption(f"Showing the first 50 of {n_ok} events.")
    if up is None and "fc_batch" in ss:
        st.caption(f"Last upload: **{ss['fc_batch'][3]}**, {len(ss['fc_batch'][0])} events. "
                   "Its forecast is in the Analysis & export tab.")

# ------------------------------------------------------------------ 3. analysis and export
with tab_an:
    if "fc_batch" not in ss:
        st.info("Upload a list of events in the **Upload a list** tab first.")
    else:
        events, pred, problems, fname = ss["fc_batch"]
        data = events.drop(columns="row").join(pred)

        f1, f2 = st.columns(2)
        types = f1.multiselect("Event type", sorted(data.event_type.unique()), default=sorted(data.event_type.unique()))
        meals = f2.multiselect("Meal", sorted(data.meal_type.unique()), default=sorted(data.meal_type.unique()))
        view = data[data.event_type.isin(types) & data.meal_type.isin(meals)]
        if view.empty:
            st.warning("No events match these filters.")
            st.stop()

        food = [c for c in CATEGORIES if c != "beverages"]
        safe_kg = sum(view[f"{c}_safe"].sum() for c in food)
        extra_kg = safe_kg - sum(view[f"{c}_expected"].sum() for c in food)
        k1, k2, k3, k4 = st.columns(4)
        kpi(k1, "Events", len(view), f"from {fname}")
        kpi(k2, "Booked guests", f"{view.guests_expected.sum():,}", f"avg {view.guests_expected.mean():.0f} per event")
        kpi(k3, "Food to prepare (safe)", f"{safe_kg:,.0f} kg", f"+ {view.beverages_safe.sum():,.0f} L beverages")
        kpi(k4, "Extra for safety", f"{extra_kg:,.0f} kg", f"{extra_kg / max(safe_kg - extra_kg, 1):.0%} above expected",
            tone="gold")
        st.write("")

        table = category_table(view)
        table["Safe per guest (g / ml)"] = table["Safe (P85)"] / view.guests_expected.sum() * 1000
        st.markdown("#### By food category")
        left, right = st.columns([3, 2])
        with left:
            bar_chart(table)
        with right:
            st.dataframe(table, hide_index=True, width="stretch",
                         column_config={k: st.column_config.NumberColumn(format="%.0f")
                                        for k in ("Expected", "Safe (P85)", "Extra for safety", "Safe per guest (g / ml)")})

        st.markdown("#### By month (safe amount, kg)")
        month = view.assign(Month=pd.to_datetime(view.event_date).dt.strftime("%Y-%m"))
        by_month = month.groupby("Month")[[f"{c}_safe" for c in food]].sum().rename(columns=lambda k: LABEL[k[:-5]])
        st.bar_chart(by_month, height=260, color=["#c9a24a", "#7a1f2b", "#5b8c5a", "#d98c5f"])

        st.markdown("#### By event type")
        by_type = view.groupby("event_type").agg(
            Events=("event_id", "size"), Guests=("guests_expected", "sum"),
            **{f"{LABEL[c]} safe ({UNIT[c]})": (f"{c}_safe", "sum") for c in CATEGORIES}).reset_index()
        st.dataframe(by_type.rename(columns={"event_type": "Event type"}), hide_index=True, width="stretch",
                     column_config={k: st.column_config.NumberColumn(format="%.0f") for k in by_type.columns[3:]})

        with st.expander(f"All {len(view)} events"):
            st.dataframe(view, hide_index=True, width="stretch")

        st.markdown("#### Download")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
            view.to_excel(xw, sheet_name="Forecast per event", index=False)
            table.to_excel(xw, sheet_name="Totals by category", index=False)
            by_month.reset_index().to_excel(xw, sheet_name="By month", index=False)
            by_type.to_excel(xw, sheet_name="By event type", index=False)
            if len(problems):
                problems.to_excel(xw, sheet_name="Rows not forecast", index=False)
            for sheet in xw.sheets.values():
                sheet.set_column(0, 30, 16)
        d1, d2, _ = st.columns([1, 1, 2])
        d1.download_button("📗 Full report (Excel)", buf.getvalue(), "food_forecast_report.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           type="primary", width="stretch")
        d2.download_button("📄 Forecast per event (CSV)", view.to_csv(index=False).encode(),
                           "food_forecast_events.csv", "text/csv", width="stretch")
