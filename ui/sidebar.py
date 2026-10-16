"""Persistent navigation controls and run buttons shared by every page."""
import streamlit as st
from cids.config import Settings
from cids.event_generator import SCENARIOS
from cids.simulation import run
from .context import controller


def render_sidebar():
    state=controller()
    ref_values={"ctl_scenario":"distributed","ctl_seed":7}
    for key,value in ref_values.items(): st.session_state.setdefault(key,value)
    with st.sidebar:
        color={"Idle":"#667085","Running":"#2563EB","Finished":"#16A34A","Error":"#DC2626"}.get(state.status,"#667085")
        st.markdown(f"<span style='color:{color};font-size:12px;font-weight:600'>● {state.status} · run {state.run_number}</span>",unsafe_allow_html=True)
        with st.expander("Run",expanded=True):
            scenario=st.selectbox("Scenario",("all",)+SCENARIOS,key="ctl_scenario",help="Seeded synthetic event and fault-injection workload.")
            seed=st.number_input("Starting seed",0,100000,key="ctl_seed",help="Seed used for a single run or first experiment run.")
            st.caption("Fixed lab: 4 localhost nodes · HMAC validation · local OR 2-peer agreement")
        st.button("Reset",key="reset_reference",on_click=lambda: [st.session_state.__setitem__(key,value) for key,value in ref_values.items()])
        running=state.status=="Running"
        run_single=st.button("Run simulation",type="primary",width="stretch",disabled=running,help="Run the selected scenario once with the configured settings.")
        stop=st.button("Stop",width="stretch",disabled=not running,help="Request a graceful stop at the next simulation checkpoint.")
        snapshot={"scenario":scenario,"seed":int(seed)}
        st.session_state.cids_settings_snapshot=snapshot
    if stop: state.stop()
    if run_single:
        try:
            settings=Settings(seed=int(seed)).validate()
            started=state.start("single",lambda event,sink:run(settings,scenario,event,sink))
            if started: st.rerun()
        except Exception as exc: state.error=f"{type(exc).__name__}: {exc}"; state.status="Error"
    state.poll()
