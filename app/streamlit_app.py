
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from features import EVENT_TYPES, MEAL_TYPES  
from predict import predict_event  

CATEGORY_LABELS = {
    "rice_starch": "Rice & Starch",
    "mains": "Mains",
    "veg_sides": "Vegetable Sides",
    "desserts": "Desserts",
    "beverages": "Beverages",
}

st.set_page_config(page_title="Hotel Food Demand Forecast", page_icon="🍽️")
st.title("🍽️ Banquet Food Demand Forecast")
st.caption(
    "Predicts expected food quantities per category, plus a safe (85th "
    "percentile) quantity that covers demand on all but the worst ~15% of events."
)

with st.form("event_form"):
    col1, col2 = st.columns(2)
    with col1:
        event_date = st.date_input("Event date")
        event_type = st.selectbox("Event type", EVENT_TYPES)
    with col2:
        meal_type = st.selectbox("Meal type", MEAL_TYPES)
        guests_expected = st.number_input("Expected guests", min_value=1, value=100, step=10)

    submitted = st.form_submit_button("Predict")

if submitted:
    event = {
        "event_date": event_date.isoformat(),
        "event_type": event_type,
        "meal_type": meal_type,
        "guests_expected": guests_expected,
    }

    try:
        predictions = predict_event(event)
    except FileNotFoundError as e:
        st.error(f"No trained models found. {e}")
        st.stop()

    results_df = pd.DataFrame(
        [
            {
                "Category": CATEGORY_LABELS[cat],
                "Expected": qty["expected"],
                "Safe (P85)": qty["safe"],
            }
            for cat, qty in predictions.items()
        ]
    ).set_index("Category")

    st.subheader("Predicted quantities (kg, beverages in litres)")
    st.dataframe(results_df, width="stretch")

    st.subheader("Expected vs. safe quantity per category")
    st.bar_chart(results_df)

    st.caption(
        "Safe quantity = the 85th-percentile prediction. Running short costs "
        "more than a modest surplus, so 'safe' is deliberately higher than 'expected'."
    )
