"""Persistent navigation controls and run buttons shared by every page."""
import json
from pathlib import Path
import streamlit as st
from cids.config import Settings
from cids.event_generator import SCENARIOS
from cids.experiments import run_experiments
from cids.simulation import run
from .context import controller

def render_sidebar():
    state=controller()
    reference=json.loads((Path(__file__).resolve().parents[1]/"configs"/"reference.json").read_text(encoding="utf-8"))
    defaults={"ctl_nodes":reference["nodes"],"ctl_tls":reference["tls"],"ctl_speed":reference["simulation_speedup"],"ctl_local_threshold":reference["rate_threshold"],"ctl_reporting_threshold":reference["reporting_threshold"],"ctl_corr":reference["correlation_window_seconds"],"ctl_decision":reference["decision_threshold"],"ctl_min_sources":reference["min_peer_sources"],"ctl_scenario":reference["scenario"],"ctl_duration":reference["duration_seconds"],"ctl_seed":reference["seed"],"ctl_seed_count":reference["seed_count"]}
    for key,value in defaults.items(): st.session_state.setdefault(key,value)
    with st.sidebar:
        color={"Idle":"#667085","Running":"#2563EB","Finished":"#16A34A","Error":"#DC2626"}.get(state.status,"#667085")
        st.markdown(f"<span style='color:{color};font-size:12px;font-weight:600'>● {state.status} · run {state.run_number}</span>",unsafe_allow_html=True)
        with st.expander("Network",expanded=False):
            nodes=st.slider("Nodes",2,10,key="ctl_nodes")
            tls=st.toggle("TLS",key="ctl_tls")
            speed=st.slider("Simulation speed",10,500,key="ctl_speed")
        max_sources=max(1,nodes-1)
        if st.session_state.ctl_min_sources>max_sources: st.session_state.ctl_min_sources=max_sources
        with st.expander("Detection",expanded=False):
            threshold=st.slider("Local threshold",2,20,key="ctl_local_threshold")
            reporting=st.slider("Reporting threshold",.1,1.,.1,key="ctl_reporting_threshold")
            correlation=st.slider("Correlation window (s)",1,60,key="ctl_corr")
            decision=st.slider("Decision threshold",.3,.9,.05,key="ctl_decision")
            sources=st.slider("Minimum peer sources",1,max_sources,key="ctl_min_sources")
        with st.expander("Run",expanded=True):
            scenario=st.selectbox("Scenario",("all",)+SCENARIOS,key="ctl_scenario")
            duration=st.slider("Duration (s)",30,600,30,key="ctl_duration")
            seed=st.number_input("Starting seed",0,100000,key="ctl_seed")
            seeds=st.number_input("Number of seeds",1,50,key="ctl_seed_count")
        st.button("Reset to reference",on_click=lambda:[st.session_state.__setitem__(k,v) for k,v in defaults.items()])
        running=state.status=="Running"; single=st.button("Run simulation",type="primary",width="stretch",disabled=running)
        left,right=st.columns(2); multi=left.button("Multi-seed",width="stretch",disabled=running); stop=right.button("Stop",width="stretch",disabled=not running)
        snapshot={"nodes":nodes,"tls":tls,"speedup":float(speed),"rate_threshold":threshold,"reporting_threshold":reporting,"correlation_window":float(correlation),"decision_threshold":float(decision),"min_peer_sources":sources,"scenario":scenario,"duration_seconds":float(duration),"seed":int(seed),"seed_count":int(seeds)}
        st.session_state.cids_settings_snapshot=snapshot
    if stop: state.stop()
    options={"tls":tls,"speedup":float(speed),"rate_threshold":threshold,"reporting_threshold":reporting,"correlation_window":float(correlation),"quorum_weight":float(decision),"min_peer_sources":sources,"duration_seconds":float(duration)}
    if single:
        try:
            settings=Settings(node_count=nodes,seed=int(seed),**options).validate()
            if state.start("single",lambda event,sink:run(settings,scenario,event,sink)): st.rerun()
        except Exception as exc: state.error=f"{type(exc).__name__}: {exc}"; state.status="Error"
    if multi:
        try:
            Settings(node_count=nodes,seed=int(seed),**options).validate()
            if state.start("multi_seed",lambda event,sink:run_experiments(count=int(seeds),start_seed=int(seed),scenario=scenario,nodes=nodes,settings_options=options,stop_event=event)): st.rerun()
        except Exception as exc: state.error=f"{type(exc).__name__}: {exc}"; state.status="Error"
    state.poll()
