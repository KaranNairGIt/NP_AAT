"""Multipage CIDS dashboard; all mutable run state belongs to its session controller."""
import streamlit as st
from ui.sidebar import render_sidebar

st.set_page_config(page_title="CIDS Console",layout="wide")
from ui.components import inject_styles
from ui.charts import register_plotly_template
inject_styles()
register_plotly_template()
pages=[
    st.Page("ui/pages/overview.py",title="Overview",icon=":material/dashboard:",default=True),
    st.Page("ui/pages/live_network.py",title="Live Network",icon=":material/hub:"),
    st.Page("ui/pages/incidents.py",title="Incidents",icon=":material/report:"),
    st.Page("ui/pages/trust.py",title="Trust",icon=":material/verified_user:"),
    st.Page("ui/pages/security.py",title="Security",icon=":material/security:"),
    st.Page("ui/pages/evaluation.py",title="Evaluation",icon=":material/analytics:"),
    st.Page("ui/pages/experiments.py",title="Experiments & Export",icon=":material/download:"),
    st.Page("ui/pages/about.py",title="About",icon=":material/info:"),
]
navigation=st.navigation(pages,position="sidebar")
render_sidebar()
navigation.run()
