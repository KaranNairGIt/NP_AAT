"""Incident-window scoring shared by CLI, exports, and dashboard."""
import statistics
from .metrics import classification
from .baselines import majority_peer_vote, majority_vote_observers

def _inside(ts, incident, grace):
    return incident["start_time"] <= ts <= incident["end_time"] + grace

def evaluate_incidents(incidents, collaborative_decisions, local_by_node, validated_alerts, node_ids, grace, local_events_by_node=None):
    rows=[]; latency=[]; truth=[]; collaborative=[]; local_any=[]; majority=[]; majority_observers=[]; node_predictions={n:[] for n in node_ids}
    local_events_by_node=local_events_by_node or {node:[] for node in node_ids}
    for incident in incidents:
        key=(incident["target_id"],incident["event_type"]); related=[d for d in collaborative_decisions if (d["target_id"],d["event_type"])==key and _inside(d["timestamp"],incident,grace)]
        positives=sorted((d for d in related if d["is_attack"]),key=lambda d:d["timestamp"]); is_detected=bool(positives)
        chosen=positives[0] if positives else (max(related,key=lambda d:d.get("weighted_support",0)) if related else {})
        local_flags={}
        for node in node_ids:
            local_flags[node]=any((d["target_id"],d["event_type"])==key and _inside(d["timestamp"],incident,grace) for d in local_by_node.get(node,[]))
            node_predictions[node].append(local_flags[node])
        alert_sources={a.sender_id for a in validated_alerts if (a.target_id,a.event_type)==key and _inside(a.timestamp,incident,grace)}
        local_nodes=sorted(node for node,flag in local_flags.items() if flag)
        majority_result=majority_peer_vote(incident,validated_alerts,node_ids,grace)
        observer_majority=majority_vote_observers(incident,validated_alerts,local_events_by_node,node_ids,grace)
        majority_yes=majority_result["decision"]; majority_observers_yes=observer_majority["decision"]
        is_truth=bool(incident["is_attack"]); truth.append(is_truth); collaborative.append(is_detected); local_any.append(any(local_flags.values())); majority.append(majority_yes); majority_observers.append(majority_observers_yes)
        fraction=sum(local_flags.values())/len(node_ids) if node_ids else 0.0
        explanation=chosen.get("explanation", "No decision in incident scoring window.")
        decision_path=(f"own local detection by {', '.join(local_nodes)}" if local_nodes else
                       f"peer evidence: weighted support {chosen.get('peer_weighted_support', 0.0):.3f}, "
                       f"{len(set(chosen.get('peer_sources', [])))} distinct sources, threshold {chosen.get('decision_threshold', .5):.3f}" if is_detected else
                       "No decision in the incident scoring window.")
        support=chosen.get("weighted_support",0.0); sources=chosen.get("sources",[])
        rows.append({"incident_id":incident["incident_id"],"target_id":incident["target_id"],"event_type":incident["event_type"],"is_attack":is_truth,"collaborative":is_detected,"local_only_any":any(local_flags.values()),"local_only_per_node_average":fraction,"majority_vote":majority_yes,"majority_vote_observers":majority_observers_yes,"weighted_support":support,"peer_weighted_support":chosen.get("peer_weighted_support",0.0),"distinct_sources":len(set(sources)) if chosen else len(alert_sources),"majority_sources":len(majority_result["supporting_node_ids"]),"observer_sources":len(observer_majority["supporting_node_ids"]),"observing_node_ids":", ".join(observer_majority["observer_node_ids"]),"supporting_node_ids":", ".join(sorted(set(sources) if sources else alert_sources)),"local_detection_nodes":", ".join(local_nodes),"decision_path":decision_path,"explanation":explanation})
        first=positives[0]["timestamp"] if positives else None
        correct_time=first if is_truth and first is not None else None
        latency.append({"incident_id":incident["incident_id"],"is_attack":is_truth,"start_time":incident["start_time"],"end_time":incident["end_time"],"grace_period_seconds":grace,"first_correct_detection_time":correct_time,"latency_seconds":(correct_time-incident["start_time"]) if correct_time is not None else None,"detected_within_grace":is_detected if is_truth else None})
    scores={"collaborative":classification(truth,collaborative),"local_only_any":classification(truth,local_any),"majority_vote":classification(truth,majority),"majority_vote_observers":classification(truth,majority_observers)}
    per_node_scores=[classification(truth,node_predictions[n]) for n in node_ids]
    metrics=("tp","tn","fp","fn","precision","recall","f1","accuracy","false_positive_rate")
    macro_metrics=("precision","recall","f1","accuracy","false_positive_rate")
    scores["local_only_per_node_average"]={m:(sum(item[m] for item in per_node_scores)/len(per_node_scores) if per_node_scores else 0.0) for m in macro_metrics}
    score_std={m:(statistics.stdev(item[m] for item in per_node_scores) if len(per_node_scores)>1 else 0.0) for m in macro_metrics}
    return {"classification":scores,"classification_std":{"local_only_per_node_average":score_std},"per_node_classification":dict(zip(node_ids,per_node_scores)),"decision_table":rows,"latency_table":latency}
