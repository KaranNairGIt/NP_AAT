from pathlib import Path
import json
import pandas as pd
from ui.components import dataframe

import streamlit as st

from ui.components import card
from ui.context import page_start

page_start("About", "Decision rules, scoring units, and simulation boundaries")
text=(Path(__file__).resolve().parents[2]/"README.md").read_text(encoding="utf-8")
sections={}; current=None
for line in text.splitlines():
    if line.startswith("#"):
        title=line.lstrip("# ")
        current=title if title in {"Decision and trust rules","Evaluation units and timing","Design and measurements","Scope note"} else None
        if current: sections[current]=[]
    elif current is not None:
        sections[current].append(line)

for title in ("Decision and trust rules","Evaluation units and timing","Scope note"):
    body=sections.get(title,[])
    if not body: continue
    with card(title):
        chunks=[]; text_lines=[]; formula=[]; in_formula=False
        for line in body:
            if line.strip()=="$$":
                in_formula=not in_formula
                if in_formula and text_lines:
                    chunks.append(("text","\n".join(text_lines))); text_lines=[]
                elif not in_formula and formula:
                    chunks.append(("math"," ".join(formula))); formula=[]
                continue
            if in_formula: formula.append(line.strip()); continue
            if line.strip(): text_lines.append(line)
        if text_lines: chunks.append(("text","\n".join(text_lines)))
        for kind,value in chunks:
            if kind=="math":
                st.latex(value)
            else:
                st.markdown(value)

reference=json.loads((Path(__file__).resolve().parents[2]/"configs"/"reference.json").read_text(encoding="utf-8"))
with card("Reference configuration"):
    rows=[{"Setting":label,"Value":str(reference[key])} for key,label in (("nodes","Nodes"),("scenario","Scenario"),("seed","Starting seed"),("seed_count","Seed count"),("duration_seconds","Duration (s)"),("simulation_speedup","Speedup"),("rate_threshold","Local threshold"),("reporting_threshold","Reporting threshold"),("correlation_window_seconds","Correlation window (s)"),("decision_threshold","Decision threshold"),("min_peer_sources","Minimum peer sources"),("tls","TLS") )]
    dataframe(pd.DataFrame(rows),height=360)
    st.caption(reference["threshold_provenance"])
with card("Limitations"):
    st.markdown("This is a deterministic synthetic lab with loopback-only sockets. It does not inspect real traffic. Results depend on the event visibility model and configured scoring window. CPU and memory include Streamlit overhead when run from the dashboard and vary by machine.")
