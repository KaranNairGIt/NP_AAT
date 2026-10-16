"""Consistent chart styling and labels for all pages."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

METHOD_COLORS={"collaborative":"#2563EB","local_only_any":"#64748B","local_only_per_node_average":"#94A3B8","majority_vote":"#D97706","majority_vote_observers":"#7C3AED"}
METHOD_LABELS={"collaborative":"Collaborative (two-peer rule)","local_only_any":"Local only (any node)","local_only_per_node_average":"Local only (per-node average)","majority_vote":"Majority vote (all nodes)","majority_vote_observers":"Majority vote (observers)"}
DISPLAY={"tp":"True positives","tn":"True negatives","fp":"False positives","fn":"False negatives","precision":"Precision","recall":"Recall","f1":"F1 score","accuracy":"Accuracy","false_positive_rate":"False positive rate","mean":"Mean","std":"Standard deviation"}

def trust_history_frame(trust_history,nodes,observer):
    """Return a stepped observer-specific history with every peer initialized at t=0."""
    rows=[]
    updates=[item for item in trust_history if item["observer_id"]==observer]
    for peer in nodes:
        if peer==observer: continue
        rows.append({"simulation_time":0.0,"to":.5,"peer_id":peer})
        peer_updates=sorted((item for item in updates if item["peer_id"]==peer),key=lambda item:item["simulation_time"])
        rows.extend({"simulation_time":float(item["simulation_time"]),"to":float(item["to"]),"peer_id":peer} for item in peer_updates)
    return pd.DataFrame(rows)

def topology_initial_time(result):
    """Use the first offline fault time as the topology slider's useful default."""
    offline=[float(item["start_time"]) for item in result.get("incidents",[]) if item["incident_id"]=="inc-offline"]
    return offline[0] if offline else 0.0


def register_plotly_template():
    template=go.layout.Template(layout=go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        font={"family":"Inter, Arial, sans-serif","color":"#475467","size":13},
        colorway=["#2563EB","#64748B","#94A3B8","#D97706","#7C3AED"],
        margin={"l":18,"r":18,"t":20,"b":50},height=330,
        legend={"orientation":"h","yanchor":"top","y":-0.18,"xanchor":"left","x":0,"title_text":""},
        xaxis={"gridcolor":"#EEF0F3","zerolinecolor":"#EEF0F3","linecolor":"rgba(0,0,0,0)"},
        yaxis={"gridcolor":"#EEF0F3","zerolinecolor":"#EEF0F3","linecolor":"rgba(0,0,0,0)"},
    ))
    pio.templates["cids_light"]=template
    pio.templates.default="cids_light"


register_plotly_template()

def metric_frame(result):
    rows=[]
    for method,metrics in result["classification"].items():
        stds=result.get("classification_std",{}).get(method,{})
        row={"Method":METHOD_LABELS.get(method,method)}
        for key,value in metrics.items(): row[DISPLAY.get(key,key)]=value
        for key,value in stds.items(): row[f"{DISPLAY.get(key,key)} (across nodes std)"]=value
        rows.append(row)
    return pd.DataFrame(rows)

def comparison_chart(result,metrics=("f1","false_positive_rate"),title="Method comparison",methods=None):
    rows=[]
    selected=methods or result["classification"].keys()
    for method in selected:
        values=result["classification"][method]
        for metric in metrics:
            if metric in values: rows.append({"Method":METHOD_LABELS.get(method,method),"Metric":DISPLAY.get(metric,metric),"Value":values[metric]})
    frame=pd.DataFrame(rows)
    fig=px.bar(frame,x="Value",y="Metric",color="Method",color_discrete_map={METHOD_LABELS[k]:v for k,v in METHOD_COLORS.items()},orientation="h",text_auto=".3f",barmode="group")
    fig.update_layout(title=None,barmode="group",height=max(330,46*len(metrics)),margin={"l":18,"r":45,"t":15,"b":55}); fig.update_traces(textposition="outside",cliponaxis=False)
    return fig

def summary_sentence(result):
    scores=result["classification"]
    collab=scores["collaborative"]; local=scores["local_only_any"]
    detected=collab["tp"]; total=collab["tp"]+collab["fn"]
    f1=collab["f1"]; fpr=collab["false_positive_rate"]
    better="higher" if collab["f1"]>local["f1"] else "lower" if collab["f1"]<local["f1"] else "equal"
    return (f"Collaborative detection found {detected:g} of {total:g} attack incidents (F1 {f1:.3f}, false-positive rate {fpr:.3f}). "
            f"Its F1 is {better} than local-only-any ({local['f1']:.3f}). "
            f"Peer-only decisions require {result.get('min_peer_sources',2)} sources; local threshold detections use self-evidence.")

def network_figure(result,at_time):
    nodes=result["nodes"]; count=max(1,len(nodes)); positions={n:(__import__("math").cos(2*__import__("math").pi*i/count),__import__("math").sin(2*__import__("math").pi*i/count)) for i,n in enumerate(nodes)}
    edges=[]
    for item in result.get("topology_history",result.get("topology",[])):
        start=item.get("start_time",0); end=item.get("end_time")
        if start<=at_time and (end is None or at_time<=end): edges.append(item)
    fig=go.Figure()
    for e in edges:
        x0,y0=positions[e["source"]]; x1,y1=positions[e["target"]]; reachable=e["status"]=="reachable"; color="#98A2B3" if reachable else "#DC2626"
        fig.add_trace(go.Scatter(x=[x0,x1],y=[y0,y1],mode="lines",line={"color":color,"width":1.5,"dash":"solid" if reachable else "dash"},hovertemplate=f"{e['source']} ↔ {e['target']} · {e['status']}<extra></extra>",showlegend=False))
    offline={n for e in edges if e["status"]!="reachable" for n in (e["source"],e["target"])}
    labels=[]; colors=[]; symbols=[]
    for n in nodes:
        labels.append(n+ (" · misleading" if n==result.get("misleading_peer_id") else " · offline" if n in offline else ""))
        colors.append("#F2F4F7" if n in offline else "#FFFFFF")
        symbols.append("circle")
    outlines=["#D97706" if n==result.get("misleading_peer_id") else "#98A2B3" if n in offline else "#2563EB" for n in nodes]
    fig.add_trace(go.Scatter(x=[positions[n][0] for n in nodes],y=[positions[n][1] for n in nodes],mode="markers+text",text=labels,textposition="bottom center",marker={"size":30,"color":colors,"symbol":symbols,"line":{"color":outlines,"width":2}},hovertemplate="%{text}<extra></extra>",showlegend=False))
    fig.update_layout(title=None,xaxis={"visible":False},yaxis={"visible":False,"scaleanchor":"x","scaleratio":1},height=400,margin={"l":10,"r":10,"t":20,"b":35},plot_bgcolor="rgba(0,0,0,0)",paper_bgcolor="rgba(0,0,0,0)",template="cids_light",annotations=[{"x":0,"y":-0.12,"xref":"paper","yref":"paper","text":"Reachable · dashed red: unavailable · amber border: misleading · grey: offline","showarrow":False,"font":{"size":11,"color":"#667085"}}])
    return fig
