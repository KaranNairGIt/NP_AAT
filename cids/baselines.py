"""Incident-level baseline helpers."""
from collections import defaultdict

def majority_peer_vote(incident,validated_alerts,node_ids,grace_period):
    """Strict majority of distinct senders represented by validated alerts."""
    start=incident["start_time"]; end=incident["end_time"]+grace_period
    senders={a.sender_id for a in validated_alerts if a.severity>=3 and a.target_id==incident["target_id"] and a.event_type==incident["event_type"] and start<=a.timestamp<=end}
    return {"decision":len(senders)>len(node_ids)/2,"supporting_node_ids":sorted(senders),"distinct_sources":len(senders)}

def majority_vote_observers(incident,validated_alerts,local_events_by_node,node_ids,grace_period):
    start=incident["start_time"]; end=incident["end_time"]+grace_period
    target=incident["target_id"]; kind=incident["event_type"]
    # The comparison population is nodes with at least one locally observed
    # event for this target during the scoring window, regardless of whether
    # their local detector crossed its alert threshold.
    observers={node for node,events in local_events_by_node.items() if any(e.target_id==target and start<=e.timestamp<=end for e in events)}
    senders={a.sender_id for a in validated_alerts if a.severity>=3 and a.target_id==target and a.event_type==kind and start<=a.timestamp<=end}
    voting_senders=senders & observers
    return {"decision":bool(observers) and len(voting_senders)>len(observers)/2,
            "supporting_node_ids":sorted(voting_senders),"distinct_sources":len(voting_senders),
            "observer_node_ids":sorted(observers),"observer_count":len(observers)}

def evaluate_baselines(events,threshold=6,window=10):
    """Expose raw local rate-rule decisions keyed by target/type/source."""
    buckets=defaultdict(list)
    for event in events: buckets[(event.target_id,event.event_type,event.source_id)].append(event)
    result={}
    for (target,kind,node),items in buckets.items():
        hits=[]
        for event in items:
            count=sum(1 for other in items if event.timestamp-window<=other.timestamp<=event.timestamp)
            if count>=threshold: hits.append({"timestamp":event.timestamp,"target_id":target,"event_type":kind,"node_id":node})
        if hits: result.setdefault(node,[]).extend(hits)
    return result
