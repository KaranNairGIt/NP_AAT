import pandas as pd
import streamlit as st
from ui.context import page_start,number
from ui.charts import METHOD_LABELS,comparison_chart,summary_sentence
from ui.components import card,dataframe

state,result=page_start("Overview","CIDS multi-observer intrusion-detection simulation")
if result is not None:
    scores=result["classification"]; rows=result["decision_table"]
    attacks=sum(bool(row["is_attack"]) for row in rows); benign=len(rows)-attacks
    display=[]
    for method in ("local_only_any","collaborative"):
        label=METHOD_LABELS[method]
        metrics=scores[method]
        if method=="local_only_per_node_average":
            attack_detected=false_alarms="—"
            attack_rate=metrics["recall"]; fpr=metrics["false_positive_rate"]
        else:
            attack_detected=f"{metrics['tp']:,} / {attacks:,}"
            false_alarms=f"{metrics['fp']:,} / {benign:,}"
            attack_rate=metrics["recall"]; fpr=metrics["false_positive_rate"]
        display.append({"Method":label,"Attacks detected":attack_detected,"False alarms":false_alarms,"Attack recall":attack_rate,"False-positive rate":fpr})
    with card("Incident outcomes"):
        st.caption("Four fixed localhost nodes exchange only authenticated alerts. The key comparison is local-only versus collaboration.")
        frame=pd.DataFrame(display)
        config={"Method":st.column_config.TextColumn("Method",help="Named evaluation method."),
                "Attacks detected":st.column_config.TextColumn("Attacks detected",help="True positives / attack incidents; shown as — for the macro per-node average."),
                "False alarms":st.column_config.TextColumn("False alarms",help="False positives / benign incidents; shown as — for the macro per-node average."),
                "Attack recall":st.column_config.NumberColumn("Attack recall",format="%.3f",help="Fraction of attack incidents detected; macro-averaged across nodes for the per-node baseline."),
                "False-positive rate":st.column_config.NumberColumn("False-positive rate",format="%.3f",help="Fraction of benign evaluation units incorrectly marked as attacks.")}
        dataframe(frame,height=250,config=config)
    summary=st.columns(4)
    summary[0].metric("Collaborative F1",number(scores["collaborative"]["f1"]),help="Harmonic mean of collaborative precision and recall over incident units.")
    summary[1].metric("Collaborative false-positive rate",number(scores["collaborative"]["false_positive_rate"]),help="False positive rate among benign evaluation incidents.")
    summary[2].metric("Alerts sent / validated",f"{result['alert_delivery']['alerts_transmitted']:,} / {result['alert_delivery']['validated_alerts_received']:,}",help="Alert transmissions and authenticated, accepted alert receipts.")
    summary[3].metric("Rejected messages and frames",f"{sum(result.get('rejection_counts',{}).values()):,}",help="Rejected messages and malformed frames counted by reason.")
    with card("Baseline comparison"):
        st.plotly_chart(comparison_chart(result,("precision","recall","f1","false_positive_rate"),"Local-only vs collaborative detection"),width="stretch")
        st.write(summary_sentence(result))
