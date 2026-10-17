"""Shared look and feel for every page: colours, header banner, KPI cards and section titles."""
import html

import streamlit as st

CSS = """
<style>
:root { --brand:#7a1f2b; --brand-2:#a3333f; --gold:#c9a24a; --cream:#fbf6ec; --ink:#2a2522; --muted:#6b5b45;
        --line:#ead9b6; }
.block-container { padding-top: 1.4rem; max-width: 1400px; }
h1, h2, h3, h4 { color: var(--ink); letter-spacing: .2px; }

.hero { background: linear-gradient(120deg, var(--brand) 0%, var(--brand-2) 60%, var(--gold) 140%); color:#fff;
        padding: 18px 26px; border-radius: 16px; margin-bottom: 16px; box-shadow: 0 6px 18px rgba(122,31,43,.18); }
.hero h1 { color:#fff; font-size: 1.85rem; margin: 0; }
.hero p { margin: 4px 0 0 0; opacity: .92; font-size: .98rem; }

.kpi { background:#fff; border:1px solid var(--line); border-left:6px solid var(--brand); border-radius:14px;
       padding:12px 16px; height:100%; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
.kpi .lab { font-size:.74rem; overflow-wrap:normal; word-break:keep-all; text-transform:uppercase; letter-spacing:.7px; color:var(--muted); }
.kpi .val { font-size:clamp(1.05rem, 1.9vw, 1.7rem); font-weight:700; color:var(--brand); line-height:1.25;
            white-space:nowrap; }
.kpi .sub { font-size:.8rem; color:var(--muted); }
.kpi.gold { border-left-color: var(--gold); }
.kpi-row { display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:12px; margin-bottom:6px; }
.kpi.gold .val { color:#8a6a1f; }

.sec { background: var(--brand); color:#fff; padding:6px 12px; border-radius:8px; font-weight:600;
       margin:10px 0 4px 0; letter-spacing:.5px; }
.grp { font-weight:700; color:var(--brand); font-size:1.12rem; border-bottom:2px solid var(--gold); margin:14px 0 6px 0; }
.note { background:#fff8e6; border:1px solid #f0d58c; padding:10px 14px; border-radius:12px; font-size:.93rem; }
.step { display:flex; gap:10px; align-items:center; font-weight:600; color:var(--ink); margin:6px 0 2px 0; }
.step .n { background:var(--brand); color:#fff; border-radius:50%; width:26px; height:26px; display:inline-flex;
           align-items:center; justify-content:center; font-size:.85rem; }

div[data-testid="stTabs"] button p { font-size:1.02rem; font-weight:600; }
div[data-testid="stTabs"] button[aria-selected="true"] p { color: var(--brand); }
section[data-testid="stSidebar"] { border-right: 1px solid var(--line); }
div[data-testid="stForm"], div[data-testid="stFileUploader"] section {
    border-radius:14px; border-color: var(--line); background:#fff; }
.stButton > button, .stDownloadButton > button, div[data-testid="stFormSubmitButton"] > button {
    border-radius: 10px; font-weight: 600; }
div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
</style>
"""


def apply():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def kpi(col, label, value, sub="", tone=""):
    col.markdown(f'<div class="kpi {tone}"><div class="lab">{html.escape(str(label))}</div>'
                 f'<div class="val">{html.escape(str(value))}</div>'
                 f'<div class="sub">{html.escape(str(sub))}</div></div>', unsafe_allow_html=True)


def kpi_row(cards):
    """Cards that wrap onto a new line on narrow screens. cards = [(label, value, sub), ...]"""
    inner = "".join(f'<div class="kpi"><div class="lab">{html.escape(str(l))}</div>'
                    f'<div class="val">{html.escape(str(v))}</div><div class="sub">{html.escape(str(u))}</div></div>'
                    for l, v, u in cards)
    st.markdown(f'<div class="kpi-row">{inner}</div>', unsafe_allow_html=True)


def step(n, text):
    st.markdown(f'<div class="step"><span class="n">{n}</span>{html.escape(text)}</div>', unsafe_allow_html=True)
