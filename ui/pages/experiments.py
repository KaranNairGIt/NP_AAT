import json
import pandas as pd
import streamlit as st
from cids.config import Settings
from cids.experiments import run_experiments,run_threshold_sweep
from cids.simulation import run
from ui.context import page_start,controller
from ui.charts import METHOD_LABELS,DISPLAY
from ui.components import card,dataframe,method_color_table

state,result=page_start("Experiments & Export","Launch named runs and download data produced by the simulation")
snapshot=st.session_state.get("cids_settings_snapshot",{"nodes":4,"seed":7,"seed_count":5,"scenario":"all","duration_seconds":180,"speedup":100,"tls":False,"rate_threshold":6,"reporting_threshold":.5,"correlation_window":15,"decision_threshold":.5,"min_peer_sources":2})
kind=st.selectbox("Experiment",["Single scenario","Multi-seed comparison","Threshold sweep"],key="named_experiment",help="Choose one run type; threshold sweep covers decision thresholds 0.3–0.9 and peer-source quorum values 1–3.")
if st.button("Run selected experiment",type="primary",disabled=state.status=="Running",help="Start the selected scenario, multi-seed comparison, or threshold sweep in the background."):
    try:
        options={"tls":snapshot["tls"],"speedup":snapshot["speedup"],"rate_threshold":snapshot["rate_threshold"],"reporting_threshold":snapshot["reporting_threshold"],"correlation_window":snapshot["correlation_window"],"quorum_weight":snapshot["decision_threshold"],"min_peer_sources":snapshot["min_peer_sources"],"duration_seconds":snapshot["duration_seconds"]}
        Settings(node_count=snapshot["nodes"],seed=snapshot["seed"],**options).validate()
        if kind=="Single scenario": started=state.start("single",lambda event,sink:run(Settings(node_count=snapshot["nodes"],seed=snapshot["seed"],**options),snapshot["scenario"],event,sink))
        elif kind=="Multi-seed comparison": started=state.start("multi_seed",lambda event,sink:run_experiments(count=snapshot["seed_count"],start_seed=snapshot["seed"],scenario=snapshot["scenario"],nodes=snapshot["nodes"],settings_options=options,stop_event=event))
        else: started=state.start("threshold_sweep",lambda event,sink:run_threshold_sweep(count=5,start_seed=snapshot["seed"],scenario=snapshot["scenario"],nodes=snapshot["nodes"],settings_options=options,stop_event=event))
        if started: st.rerun()
    except Exception as exc: state.error=f"{type(exc).__name__}: {exc}"; state.status="Error"
state.poll()

if state.result is not None:
    with card("Latest run output"):
        if state.result_kind=="multi_seed":
            table=pd.DataFrame(state.result.get("summary",[])); shown=table.copy(); shown["method"]=shown.method.map(METHOD_LABELS); shown["metric"]=shown.metric.map(DISPLAY)
            shown=shown.rename(columns={"method":"Method","metric":"Metric","mean":"Mean","std":"Standard deviation","mean_plus_minus_std":"Mean ± standard deviation"})
            dataframe(method_color_table(shown,column="Method").format({"Mean":"{:.3f}","Standard deviation":"{:.3f}"}),height=380)
            st.download_button("Download multi-seed summary CSV",table.to_csv(index=False),"experiment_summary.csv","text/csv",help="Download method-level mean and standard deviation per metric.")
            raw=[{"seed":r["seed"],"method":m,**metrics} for r in state.result.get("runs",[]) for m,metrics in r["classification"].items()]
            st.download_button("Download per-seed CSV",pd.DataFrame(raw).to_csv(index=False),"experiment.csv","text/csv",help="Download raw metrics for each seed and method.")
        elif state.result_kind=="threshold_sweep":
            table=pd.DataFrame(state.result.get("rows",[])); dataframe(table,height=340)
            st.download_button("Download threshold sweep CSV",table.to_csv(index=False),"threshold_sweep.csv","text/csv",help="Download F1, false-positive rate, and misleading-peer support for each sweep setting.")
        else:
            table=pd.DataFrame(state.result.get("decision_table",[]))
            shown=table.copy()
            if not shown.empty:
                shown["is_attack"]=shown["is_attack"].map({True:"Attack",False:"Benign"})
                for key in ("collaborative","local_only_any","majority_vote","majority_vote_observers"):
                    shown[key]=shown[key].map({True:"Detected",False:"Missed"})
                shown=shown.drop(columns=["explanation"],errors="ignore").rename(columns={"incident_id":"Incident ID","target_id":"Target ID","event_type":"Event type","is_attack":"Ground truth","collaborative":METHOD_LABELS["collaborative"],"local_only_any":METHOD_LABELS["local_only_any"],"local_only_per_node_average":"Local only (per-node average share)","majority_vote":METHOD_LABELS["majority_vote"],"majority_vote_observers":METHOD_LABELS["majority_vote_observers"],"weighted_support":"Weighted support","peer_weighted_support":"Peer weighted support","distinct_sources":"Distinct sources","supporting_node_ids":"Supporting node IDs","local_detection_nodes":"Local detection nodes","decision_path":"Decision path","observing_node_ids":"Observing node IDs","majority_sources":"Majority sources","observer_sources":"Observer sources"})
            dataframe(shown,height=440)
            st.download_button("Download decisions CSV",table.to_csv(index=False),"incident_decisions.csv","text/csv",help="Download ground truth and method decisions per incident.")
            latency=pd.DataFrame(state.result.get("latency_table",[]))
            st.download_button("Download per-incident latency CSV",latency.to_csv(index=False),"incident_latency.csv","text/csv",help="Download first-correct-detection latency measured from each incident's start.")
        st.download_button("Download latest run JSON",json.dumps(state.result,indent=2),"cids_results.json","application/json",help="Download the complete structured result for this run.")
