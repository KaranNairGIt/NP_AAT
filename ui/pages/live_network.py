import pandas as pd
import plotly.express as px
import streamlit as st
from ui.context import page_start,controller,number
from ui.charts import network_figure,topology_initial_time
from ui.components import card,dataframe

state,result=page_start("Live Network","Peer reachability, observed alerts, and event/alert volume")
if result is not None:
    state.poll()
    max_time=max([result.get("duration_seconds",180)]+[float(i["end_time"])+result.get("grace_period_seconds",0) for i in result["incidents"]])
    with card("Peer topology"):
        default_time=topology_initial_time(result)
        if "net_time" not in st.session_state: st.session_state.net_time=default_time
        if st.session_state.net_time>max_time: st.session_state.net_time=float(max_time)
        at_time=st.slider("Status at simulation time (seconds)",0.0,float(max_time),step=1.0,key="net_time",help="Move through the simulation timeline to see when peer links were reachable or offline.")
        starts=[f"{i['incident_id']}: {i['start_time']:.1f} s" for i in result.get("incidents",[])]
        st.caption("Incident start times · "+" · ".join(starts))
        st.plotly_chart(network_figure(result,at_time),width="stretch")
    counts=[]
    for node in result["nodes"]:
        counts.append({"Node":node,"Events":result.get("node_event_counts",{}).get(node,0),"Alerts":result.get("node_alert_counts",{}).get(node,0)})
    with card("Node activity"):
        bars=pd.DataFrame(counts).melt(id_vars="Node",var_name="Type",value_name="Count")
        st.plotly_chart(px.bar(bars,x="Node",y="Count",color="Type",barmode="group",color_discrete_map={"Events":"#3B82F6","Alerts":"#94A3B8"},text_auto=True),width="stretch")
    @st.fragment(run_every="1s" if state.status=="Running" else None)
    def render_live_feed():
        state.poll()
        with card("Live alert feed"):
            latest=state.result
            source=latest.get("feed",[]) if latest and state.status=="Finished" and state.result_kind=="single" else state.feed_history
            frame=pd.DataFrame(source)
            if frame.empty:
                st.caption("Waiting for alert messages…")
            else:
                cols=st.columns(4)
                columns={"node_id":"Node","target_id":"Target","event_type":"Event type","kind":"Message kind"}
                for col,(key,label) in zip(cols,columns.items()):
                    options=sorted(frame[key].dropna().astype(str).unique()) if key in frame else []
                    selected=col.multiselect(label,options,key=f"feed_filter_{key}",help=f"Filter live alert messages by {label.lower()}.")
                    if selected and key in frame: frame=frame[frame[key].astype(str).isin(selected)]
                shown=frame.tail(100).rename(columns={"simulation_time":"Simulation time (s)","kind":"Message kind","node_id":"Node ID","peer_id":"Peer ID","target_id":"Target ID","event_type":"Event type","alert_id":"Alert ID","decision":"Attack decision"})
                dataframe(shown,height=360)
    render_live_feed()
