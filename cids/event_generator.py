"""Seeded synthetic workloads with fixed incident windows and explicit visibility."""
import random
from .models import Event

SCENARIOS=("concentrated","coordinated","low_rate","benign_bait","duplicate_delayed","misleading_peer","offline_peer","replay","invalid_messages")
REFERENCE_DURATION=240.0
INCIDENTS=(("concentrated","srv-A","login_fail",5,10,True),("coordinated","srv-B","port_probe",20,30,True),("lowrate","srv-C","login_fail",40,100,True),("benign-bait","srv-D","login_fail",110,120,False),("duplicate-delayed","srv-E","http_request",130,140,False),("misleading","srv-F","port_probe",150,160,True),("offline","srv-G","login_fail",170,180,True),("replay","srv-H","port_probe",190,200,True),("invalid_messages","srv-I","login_fail",210,220,True))
FAULT_START=225.0
REQUIRED_DURATION=FAULT_START+10.0

def _owners(node_count,count=3,*,exclude=()): return [i for i in range(node_count) if i not in exclude][:min(count,node_count-len(exclude))]

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
    wanted=lambda name:scenario in ("all",name)
    if wanted("concentrated"): add(5,"srv-A","login_fail",{0:12},True,"inc-concentrated","concentrated",4)
    if wanted("coordinated"): add(20,"srv-B","port_probe",{i:3 for i in _owners(node_count,node_count)},True,"inc-coordinated","coordinated",8)
    if wanted("low_rate"): add(40,"srv-C","login_fail",{i:3 for i in range(node_count)},True,"inc-lowrate","low_rate",8)
    if wanted("benign_bait"): add(110,"srv-D","login_fail",{i:3 for i in _owners(node_count,min(4,node_count))},False,"inc-benign-bait","benign_bait",8)
    if wanted("duplicate_delayed"): add(130,"srv-E","http_request",{i:2 for i in _owners(node_count,min(3,node_count))},False,"inc-duplicate-delayed","duplicate_delayed",5)
    if wanted("misleading_peer"):
        add(150,"srv-F","port_probe",{i:3 for i in _owners(node_count,node_count-1,exclude=(0,))},True,"inc-misleading","misleading_peer",8)
        add(219,"synthetic-fault-target","benign_observation",{i:1 for i in _owners(node_count,min(3,node_count),exclude=(0,))},False,"","watch")
    if wanted("offline_peer"): add(170,"srv-G","login_fail",{i:3 for i in _owners(node_count,node_count-1,exclude=(node_count-1,))},True,"inc-offline","offline_peer",8)
    if wanted("replay"): add(190,"srv-H","port_probe",{i:3 for i in _owners(node_count,node_count)},True,"inc-replay","replay",8)
    if wanted("invalid_messages"): add(210,"srv-I","login_fail",{i:7 for i in _owners(node_count,node_count)},True,"inc-invalid","invalid_messages",8)
    return sorted(rows,key=lambda e:e.timestamp)

def incidents(scenario="all",duration_seconds=REFERENCE_DURATION,include_fault=False):
    if duration_seconds<=0: raise ValueError("duration_seconds must be positive")
    aliases={"low_rate":"lowrate","benign_bait":"benign-bait","duplicate_delayed":"duplicate-delayed"}; normalized=aliases.get(scenario,scenario)
    selected=INCIDENTS if scenario=="all" else tuple(r for r in INCIDENTS if r[0]==normalized)
    output=[{"incident_id":"inc-"+key,"target_id":target,"event_type":kind,"start_time":start,"end_time":end,"is_attack":attack} for key,target,kind,start,end,attack in selected]
    if include_fault: output.append({"incident_id":"inc-false-peer-alert","target_id":"synthetic-fault-target","event_type":"port_probe","start_time":FAULT_START,"end_time":REQUIRED_DURATION,"is_attack":False})
    return output
