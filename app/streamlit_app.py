"""RESHEEN Hotel & Banquets - app entry point. Run:  streamlit run app/streamlit_app.py

Two pages, chosen in the sidebar:
  Event Order    plan one event: Party Menu -> safe guest count -> Stock Balance -> printouts
  Food Forecast  expected and safe (P85) kg per food category, for one event or an uploaded list
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui  # noqa: E402

st.set_page_config(page_title="RESHEEN Event Order System", page_icon="🍽️", layout="wide")
ui.apply()

views = Path(__file__).resolve().parent / "views"
st.navigation([
    st.Page(views / "event_order.py", title="Event Order", icon="🍽️", default=True),
    st.Page(views / "food_forecast.py", title="Food Forecast", icon="📊"),
]).run()
