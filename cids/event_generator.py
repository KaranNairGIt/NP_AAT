"""Seeded synthetic workloads with fixed incident windows and explicit visibility."""
import random
from .models import Event

SCENARIOS=("normal","concentrated","distributed","invalid_message")
REFERENCE_DURATION=120.0
INCIDENTS=(
    ("normal","srv-normal","login_fail",5,15,False),
    ("concentrated","srv-A","login_fail",25,35,True),
    ("distributed","srv-B","port_probe",50,60,True),
    ("invalid-message","srv-safe","port_probe",80,90,False),
)
FAULT_START=85.0
REQUIRED_DURATION=90.0

def _owners(node_count, count=3, *, exclude=()):
    return [i for i in range(node_count) if i not in exclude][:min(count,node_count-len(exclude))]

def generate(seed=7,node_count=4,scenario="all",duration_seconds=REFERENCE_DURATION):
    if duration_seconds<=0: raise ValueError("duration_seconds must be positive")
    if not 2<=node_count<=10: raise ValueError("node_count must be 2..10")
    rng=random.Random(seed); rows=[]; serial=0
    def add(t,target,kind,counts,attack=False,incident="",label=None,spread=0.0):
        nonlocal serial
        for owner,count in counts.items():
            for j in range(count):
                serial+=1; offset=spread*j/max(1,count-1) if count>1 else 0.0
                rows.append(Event(f"e{serial:05d}",t+offset+rng.random()*.04,f"node-{owner}",target,kind,{"rate":1,"scenario":label or scenario},attack,incident))
    def wanted(name): return scenario in ("all",name)
    if wanted("normal"): add(5,"srv-normal","login_fail",{i:2 for i in _owners(node_count,node_count)},False,"inc-normal","normal",spread=4)
    if wanted("concentrated"): add(25,"srv-A","login_fail",{0:12},True,"inc-concentrated","concentrated",spread=4)
    if wanted("distributed"): add(50,"srv-B","port_probe",{i:3 for i in _owners(node_count,node_count)},True,"inc-distributed","distributed",spread=8)
    if wanted("invalid_message"): add(80,"srv-safe","port_probe",{i:1 for i in _owners(node_count,node_count)},False,"inc-invalid-message","invalid_message",spread=2)
    return sorted(rows,key=lambda e:e.timestamp)

def incidents(scenario="all",duration_seconds=REFERENCE_DURATION,include_fault=False):
    if duration_seconds<=0: raise ValueError("duration_seconds must be positive")
    aliases={}
    normalized=aliases.get(scenario,scenario)
    selected=INCIDENTS if scenario=="all" else tuple(r for r in INCIDENTS if r[0]==normalized)
    output=[{"incident_id":"inc-"+key,"target_id":target,"event_type":kind,"start_time":start,"end_time":end,"is_attack":attack} for key,target,kind,start,end,attack in selected]
    if include_fault: output.append({"incident_id":"inc-false-peer-alert","target_id":"synthetic-fault-target","event_type":"port_probe","start_time":FAULT_START,"end_time":REQUIRED_DURATION,"is_attack":False})
    return output
