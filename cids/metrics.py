"""Incident-level classification and operational metrics."""
def classification(truth,pred):
    pairs=list(zip(truth,pred)); tp=sum(bool(a) and bool(b) for a,b in pairs); tn=sum(not a and not b for a,b in pairs); fp=sum(not a and b for a,b in pairs); fn=sum(a and not b for a,b in pairs); div=lambda a,b:a/b if b else 0.0
    return {"tp":tp,"tn":tn,"fp":fp,"fn":fn,"precision":div(tp,tp+fp),"recall":div(tp,tp+fn),"f1":div(2*tp,2*tp+fp+fn),"accuracy":div(tp+tn,len(pairs)),"false_positive_rate":div(fp,fp+tn)}
def operational(*,events=0,alerts_sent=0,alerts_received=0,bytes_sent=0,bytes_received=0,latencies=None,cpu_percent=None,memory_bytes=None,peak_memory_bytes=None,wall_runtime_seconds=0.0,avg_message_size=0.0):
    xs=latencies or []; return {"events":events,"alerts_sent":alerts_sent,"alerts_received":alerts_received,"bytes_sent":bytes_sent,"bytes_received":bytes_received,"average_message_size_bytes":avg_message_size,"mean_latency_seconds":sum(xs)/len(xs) if xs else None,"cpu_percent":cpu_percent,"memory_bytes":memory_bytes,"peak_memory_bytes":peak_memory_bytes,"wall_runtime_seconds":wall_runtime_seconds}
