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
    st.Page("ui/pages/incidents.py",title="Detection",icon=":material/radar:"),
    st.Page("ui/pages/evaluation.py",title="Results",icon=":material/analytics:"),
]
navigation=st.navigation(pages,position="sidebar")
render_sidebar()
navigation.run()
