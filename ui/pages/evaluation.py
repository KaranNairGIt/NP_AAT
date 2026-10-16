"""Compact results page for the classroom demonstration."""
import pandas as pd
import streamlit as st

from ui.charts import comparison_chart
from ui.components import card, dataframe
from ui.context import number, page_start

state, result = page_start("Results", "A small, honest comparison of local-only and collaborative detection")
if result is not None:
    with card("Local-only versus collaboration"):
        rows=[]
        for method, label in (("local_only_any", "Local only"), ("collaborative", "Collaborative")):
            score=result["classification"][method]
            rows.append({"Method":label, "Precision":score["precision"], "Recall":score["recall"], "F1":score["f1"], "False-positive rate":score["false_positive_rate"]})
        dataframe(pd.DataFrame(rows), height=180)
        st.plotly_chart(comparison_chart(result, ("precision", "recall", "f1", "false_positive_rate"), "Detection results", ("local_only_any", "collaborative")), width="stretch")
    with card("Security checks"):
        rejected=sum(result.get("rejection_counts", {}).values())
        a, b, c = st.columns(3)
        a.metric("Rejected invalid messages", rejected)
        b.metric("Alerts sent / accepted", f"{result['alert_delivery']['alerts_transmitted']} / {result['alert_delivery']['validated_alerts_received']}")
        c.metric("Two-peer rule", "Enabled")
        if result.get("rejection_counts"):
            dataframe(pd.DataFrame([{"Reason":k, "Count":v} for k,v in result["rejection_counts"].items()]), height=160)
    with card("Run details"):
        st.caption(f"Seed {result['seed']} · four nodes bound to 127.0.0.1 · {number(result['operational']['bytes_sent'])} bytes sent")
