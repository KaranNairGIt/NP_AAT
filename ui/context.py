"""Small access helpers shared by multipage screens."""
import streamlit as st
from .controller import RunController


def controller():
    if "cids_controller" not in st.session_state:
        st.session_state.cids_controller=RunController()
    return st.session_state.cids_controller


def page_start(title,subtitle=None):
    state=controller(); state.poll()
    snapshot=st.session_state.get("cids_settings_snapshot",{})
    colors={"Idle":"#667085","Running":"#2563EB","Finished":"#16A34A","Error":"#DC2626"}
    left,right=st.columns([5,2],vertical_alignment="center")
    with left:
        st.markdown(f'<div class="cids-page-title">{title}</div><div class="cids-page-description">{subtitle or ""}</div><div class="cids-page-description">Simulated data — localhost only</div>',unsafe_allow_html=True)
    with right:
        @st.fragment(run_every="1s" if state.status=="Running" else None)
        def status_panel():
            previous=state.status
            state.poll()
            active=state.result or {}
            seed=active.get("seed",snapshot.get("seed","n/a"))
            scenario=active.get("scenario",snapshot.get("scenario","n/a"))
            st.markdown(f'<div style="text-align:right"><span class="cids-status-pill" style="border-color:{colors.get(state.status,colors["Idle"])}">{state.status}</span><div class="cids-page-description">Seed {seed} · Scenario: {scenario}</div></div>',unsafe_allow_html=True)
            if previous=="Running" and state.status!="Running": st.rerun()
        status_panel()
    if state.error: st.error(state.error)
    if state.result is None:
        st.markdown('<div class="cids-empty"><strong>No run yet — configure the simulation and press Run.</strong><span style="font-size:12px;margin-top:7px">Choose network, detection and scenario settings in the sidebar.</span></div>',unsafe_allow_html=True)
        return state,None
    if state.result_kind=="multi_seed":
        runs=state.result.get("runs",[]) if isinstance(state.result,dict) else []
        return state,(runs[-1] if runs else None)
    if state.result_kind=="threshold_sweep": return state,None
    return state,state.result


def number(value,digits=3):
    if value is None: return "n/a"
    try: return f"{float(value):.{digits}f}"
    except (TypeError,ValueError): return "n/a"
