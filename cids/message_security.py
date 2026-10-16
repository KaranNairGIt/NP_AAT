import hashlib,hmac,json,time,logging
from collections import OrderedDict
from dataclasses import asdict
from .models import Alert

def canonical(d): return json.dumps(d,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sign(alert,key): alert.signature=hmac.new(key,canonical(alert.unsigned()),hashlib.sha256).hexdigest(); return alert
def encode(alert): return canonical(asdict(alert))
log=logging.getLogger(__name__)
class Validator:
    def __init__(self,identities,keys,freshness=60,limit=10000): self.ids=identities; self.keys=keys; self.freshness=freshness; self.limit=limit; self.seen=OrderedDict(); self.rejections={}; self.peer_rejections={}
    def reject(self,code,peer="unknown"):
        self.rejections[code]=self.rejections.get(code,0)+1
        key=(peer,code); self.peer_rejections[key]=self.peer_rejections.get(key,0)+1
        log.warning("alert rejected peer=%s reason=%s",peer,code)
        raise ValueError(code)
    def validate(self,d,connection_peer,now):
        fields=set(Alert.__dataclass_fields__)
        if not isinstance(d,dict) or set(d)!=fields: self.reject("schema",connection_peer)
        text_fields=("alert_id","event_id","sender_id","event_type","target_id","evidence_summary","signature")
        if not all(isinstance(d[k],str) and d[k] for k in text_fields) or len(d["evidence_summary"])>256: self.reject("schema",connection_peer)
        if type(d["protocol_version"]) is not int or type(d["severity"]) is not int or not 1<=d["severity"]<=5 or type(d["confidence"]) not in (int,float) or not 0<=d["confidence"]<=1: self.reject("types_ranges",connection_peer)
        if d["protocol_version"]!=1: self.reject("protocol",connection_peer)
        sender=d["sender_id"]
        if sender not in self.ids or sender!=connection_peer: self.reject("sender",connection_peer)
        if type(d["timestamp"]) not in (int,float): self.reject("types_ranges",connection_peer)
        sig=d.pop("signature"); expected=hmac.new(self.keys[sender],canonical(d),hashlib.sha256).hexdigest(); d["signature"]=sig
        if not hmac.compare_digest(sig,expected): self.reject("signature",connection_peer)
        if abs(now-d["timestamp"])>self.freshness: self.reject("freshness",connection_peer)
        while self.seen and now-next(iter(self.seen.values()))>self.freshness: self.seen.popitem(last=False)
        key=(sender,d["alert_id"])
        if key in self.seen: self.reject("replay",connection_peer)
        self.seen[key]=now
        while len(self.seen)>self.limit: self.seen.popitem(last=False)
        return Alert(**d)
