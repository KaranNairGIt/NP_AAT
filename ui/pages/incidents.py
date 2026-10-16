import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from ui.context import page_start,number
from ui.components import card,dataframe
from ui.charts import METHOD_LABELS

state,result=page_start("Detection","Run one of four clear demonstration scenarios")
if result is not None:
    rows=result["decision_table"]
    with card("Ground truth and method decisions"):
        display=[]
        for row in rows:
            truth=bool(row["is_attack"])
            item={"incident_id":row["incident_id"],"is_attack":"Attack" if truth else "Benign",
                  "collaborative":"Detected" if row["collaborative"] else "Missed","local_only_any":"Detected" if row["local_only_any"] else "Missed",
                  "distinct_sources":row.get("distinct_sources",0),"supporting_node_ids":row.get("supporting_node_ids",""),"decision_path":row.get("decision_path","")}
            display.append(item)
        table=pd.DataFrame(display).rename(columns={"incident_id":"Incident ID","is_attack":"Ground truth",
            "collaborative":"Collaborative","local_only_any":"Local only",
            "distinct_sources":"Distinct sources","supporting_node_ids":"Supporting node IDs","decision_path":"Why"})
        dataframe(table,height=440)
    selected=st.selectbox("Inspect incident",[x["incident_id"] for x in rows],key="incident_detail",help="Choose an evaluation incident to inspect its window, evidence, support, and explanation.")
    row=next(x for x in rows if x["incident_id"]==selected)
    truth=next(x for x in result["incidents"] if x["incident_id"]==selected)
    with card("Incident details"):
        st.subheader(selected)
        c1,c2,c3=st.columns(3)
        c1.metric("Truth", "Attack" if truth["is_attack"] else "Benign",help="Ground-truth label for this evaluation incident.")
        c2.metric("Window",f"{number(truth['start_time'])}–{number(truth['end_time'])} s",help="Simulation start and end times for this labeled incident.")
        c3.metric("Grace period",f"{number(result['grace_period_seconds'])} s",help="Time after the incident end allowed for scoring an attack decision.")
        columns=st.columns(3)
        columns[0].metric("Distinct sources",row["distinct_sources"],help="Number of distinct authenticated peer senders supporting this incident. Two peer reports are required without a local detection.")
        columns[1].metric("Supporting node IDs",row["supporting_node_ids"] or "None",help="Node identities whose validated alerts contributed support.")
        columns[2].metric("Nodes observing target",row.get("observing_node_ids") or "None",help="Nodes with local observations of this incident target.")
        st.markdown("**Explanation**")
        st.write(row["decision_path"])
