from collections import defaultdict
class AlertCorrelator:
    def __init__(self,window=15): self.window=window; self.groups=defaultdict(dict)
    def add(self,alert,peer_trust,now):
        key=(alert.target_id,alert.event_type); group=self.groups[key]
        for a in list(group.values()):
            if now-a[0]>self.window: del group[a[1].sender_id]
        group[alert.sender_id]=(now,alert,peer_trust); return key
    def evidence(self,key): return list(self.groups[key].values())
