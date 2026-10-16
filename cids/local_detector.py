from collections import defaultdict,deque
class LocalDetector:
    def __init__(self,threshold=6,window=10): self.threshold=threshold; self.window=window; self.events=defaultdict(deque)
    def observe(self,event):
        key=(event.source_id,event.target_id,event.event_type); q=self.events[key]; q.append(event.timestamp)
        while q and event.timestamp-q[0]>self.window: q.popleft()
        score=min(1.0,len(q)/self.threshold); hit=len(q)>=self.threshold
        return {"score":score,"decision":hit,"explanation":f"{len(q)} {event.event_type} events from {event.source_id} in {self.window:g}s (threshold {self.threshold})"}
