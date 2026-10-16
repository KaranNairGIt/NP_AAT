from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class Event:
    event_id:str; timestamp:float; source_id:str; target_id:str; event_type:str; features:dict[str,Any]; is_attack:bool=False; incident_id:str=""
@dataclass
class Alert:
    protocol_version:int; alert_id:str; event_id:str; sender_id:str; timestamp:float; event_type:str; target_id:str; severity:int; confidence:float; evidence_summary:str; signature:str=""
    def unsigned(self): return {k:v for k,v in asdict(self).items() if k!="signature"}
@dataclass
class PeerMessage:
    sender_id:str; payload:dict[str,Any]
@dataclass
class TrustState:
    score:float=0.5; history:list= None
    def __post_init__(self): self.history=[] if self.history is None else self.history
@dataclass
class Decision:
    timestamp:float; target_id:str; event_type:str; is_attack:bool; confidence:float; sources:list[str]; explanation:str
@dataclass
class EvalRecord:
    scenario:str; incident_id:str; target_id:str; event_type:str; truth:bool; prediction:bool; confidence:float; latency:float; sources:int

def validate_event(e):
    if not isinstance(e,Event) or not e.event_id or not e.source_id or not e.target_id or not e.event_type: raise ValueError("invalid event identity")
    if e.timestamp < 0 or not isinstance(e.features,dict): raise ValueError("invalid event timestamp/features")
    return e
