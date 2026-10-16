"""Reusable visual components and readable dataframe configuration."""
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import streamlit as st


def inject_styles():
    css = (Path(__file__).parent / "styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


@contextmanager
def card(label=None):
    with st.container(border=True):
        if label:
            st.markdown(f'<div class="cids-section-label">{label}</div>', unsafe_allow_html=True)
        yield


def kpi(label, value, help_text, delta=None):
    st.metric(label, value, delta=delta, help=help_text, border=False)


def method_color_table(frame, column="method"):
    from ui.charts import METHOD_COLORS, METHOD_LABELS
    colors={**METHOD_COLORS,**{METHOD_LABELS[key]:color for key,color in METHOD_COLORS.items()}}
    return frame.style.map(lambda value:f"color: {colors[value]}; font-weight: 600" if value in colors else "",subset=[column])


def dataframe(frame, *, height=360, config=None, **kwargs):
    """Show a readable, scrollable table with mono IDs and score bars."""
    config = dict(config or {})
    source = frame.data if hasattr(frame, "data") and hasattr(frame, "_todo") else frame
    for column in source.columns:
        key = str(column).lower()
        if column in config:
            continue
        if key in {"tp","tn","fp","fn"} or key.startswith(("true positives","true negatives","false positives","false negatives")):
            config[column] = st.column_config.NumberColumn(str(column), format="%,.0f", width="small")
        elif any(token in key for token in ("trust", "confidence", "score", "precision", "recall", "f1", "rate", "per-node average")):
            config[column] = st.column_config.ProgressColumn(str(column), min_value=0, max_value=1, format="%.3f")
        elif any(token in key for token in ("incident_id", "target_id", "node_id", "supporting node", "peer_id", "observer_id")):
            config[column] = st.column_config.TextColumn(str(column), width="medium")
        elif pd.api.types.is_numeric_dtype(source[column]):
            numeric=source[column].dropna()
            if not numeric.empty and pd.api.types.is_integer_dtype(numeric.dtype):
                config[column] = st.column_config.NumberColumn(str(column), format="%,d", width="small")
            else:
                config[column] = st.column_config.NumberColumn(str(column), format="%.3f", width="small")
        else:
            config[column] = st.column_config.TextColumn(str(column), width="medium")
    fitted_height=min(height,max(80,42+35*len(source)))
    st.dataframe(frame, column_config=config, hide_index=True, height=fitted_height, width="stretch", **kwargs)
