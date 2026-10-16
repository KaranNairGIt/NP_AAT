import pandas as pd
import plotly.express as px
import streamlit as st
from ui.context import page_start
from ui.components import card,dataframe

REASONS={"replay":"A previously accepted sender alert ID was received again.","freshness":"Authenticated alert timestamp fell outside the permitted freshness window.","signature":"HMAC signature did not match the configured sender key.","empty_frame":"Frame declared zero bytes.","truncated":"Frame ended before its declared payload length arrived.","oversized_frame":"Declared frame exceeded the configured maximum size.","non_utf8":"Payload was not valid UTF-8.","invalid_json":"Payload could not be decoded as JSON.","invalid_frame":"Malformed frame header or payload.","schema":"Message fields did not match the protocol schema.","types_ranges":"A field had an invalid type or value range.","sender":"Claimed identity did not match the authenticated channel identity.","protocol":"Protocol version was unsupported.","timeout":"Handshake or frame read exceeded its timeout."}
DISPLAY={"signature":"Bad signature","freshness":"Stale timestamp","replay":"Replay","empty_frame":"Empty frame","truncated":"Truncated frame","oversized_frame":"Oversized frame","non_utf8":"Non-UTF-8 payload","invalid_json":"Invalid JSON","invalid_frame":"Invalid frame","schema":"Invalid schema","types_ranges":"Invalid field value","sender":"Sender mismatch","protocol":"Unsupported protocol","timeout":"Timeout"}

state,result=page_start("Security","Authentication, replay protection, and transport rejection evidence")
if result is not None:
    with card("Rejections by reason"):
        counts=result.get("rejection_counts",{})
        if counts:
            data=pd.DataFrame([{"Reason":("Authentication and freshness" if k in {"signature","freshness","replay"} else "Frame and format")+" · "+DISPLAY.get(k,k.replace("_"," ").title()),"Count":int(v),"Explanation":REASONS.get(k,"Protocol or peer validation rejected the message.")} for k,v in counts.items()]).sort_values("Count")
            fig=px.bar(data,x="Count",y="Reason",orientation="h",color_discrete_sequence=["#2563EB"],text="Count",template="cids_light")
            fig.update_layout(title=None,yaxis_title="",xaxis_title="Rejected messages and frames")
            st.plotly_chart(fig,width="stretch")
            data=data.rename(columns={"Reason":"Rejection reason","Explanation":"Meaning"})
            dataframe(data,height=300)
        else: st.caption("No rejections recorded.")
    with card("Channel and peer rejection log"):
        rows=[]
        for key,count in result.get("rejections",{}).items():
            if ":" in key:
                parts=key.split(":",2)
                if len(parts)==3: rows.append({"Receiver":parts[0],"Connection peer":parts[1],"Reason":parts[2],"Count":count})
        if rows: dataframe(pd.DataFrame(rows),height=300)
        else: st.caption("No channel-scoped rejections recorded.")
        st.caption("Rejected or replayed payloads cannot change the trust score of the sender identity they claim. Those events are attributed to the transport channel.")
