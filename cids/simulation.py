"""Local-only orchestration, scoring, and CLI."""
import asyncio, argparse, json, logging, struct, time
from dataclasses import asdict
from .config import Settings
from .clock import SimulationClock
from .event_generator import generate, incidents, SCENARIOS, REFERENCE_DURATION, REQUIRED_DURATION, FAULT_START
from .node import IDSNode
from .metrics import operational
from .models import Alert, Event
from .message_security import sign
from .evaluation import evaluate_incidents
log=logging.getLogger("cids")

async def _wait_until(clock,target,stop_event=None):
    while clock.now()<target:
        if stop_event is not None and stop_event.is_set(): return False
        remaining=(target-clock.now())/clock.speedup
        await asyncio.sleep(min(0.002,max(0.0001,remaining)))
    return stop_event is None or not stop_event.is_set()

async def _sample_rss(process, stop_event, samples):
    while not stop_event.is_set():
        samples.append(process.memory_info().rss)
        try: await asyncio.wait_for(stop_event.wait(), timeout=0.02)
        except asyncio.TimeoutError: pass

async def _warmup_mesh(nodes, ports, settings):
    results={}
    async def connect(source,target):
        try:
            await asyncio.wait_for(nodes[source].transport.warmup(ports[target],source,target),settings.socket_timeout_seconds)
            results[(source,target)]="reachable"
        except Exception as exc:
            results[(source,target)]="unavailable"
            log.warning("peer warm-up unavailable source=%s target=%s reason=%s",source,target,type(exc).__name__)
    await asyncio.gather(*(connect(a,b) for a in nodes for b in nodes if a!=b))
    return results

async def _inject_faults(settings,nodes,ports,keys,clock,scenario,stop_event=None):
    active=scenario in ("all","invalid_message")
    if not active: return None
    if not await _wait_until(clock,FAULT_START,stop_event): return None
    src=nodes["node-0"]; dst="node-1"; port=ports[dst]
    if False:
        watch_time=clock.now()
        await nodes[dst].submit(Event("fault-watch-node-1",watch_time,dst,"synthetic-fault-target","benign_observation",{}))
        await nodes[dst].event_queue.join()
    fault_start=clock.now()
    alert=Alert(1,"fault-alert-1","fault-event","node-0",clock.now(),"port_probe","synthetic-fault-target",4,.9,"synthetic fault-injection evidence")
    sign(alert,keys["node-0"]); payload=asdict(alert)
    if scenario in ("all","invalid_message"):
        bad=asdict(alert); bad["alert_id"]="bad-signature"; bad["signature"]="0"*64
        await src.transport.send(port,src.id,bad)
        for raw,declared in ((b"",0),(b"{bad-json",None),(b"\xff",None),(b"x"*(settings.max_frame_bytes+1),None),(b"{}",5)):
            await src.transport.send_frame(port,src.id,raw,declared)
    return None

async def run(settings,scenario="all",stop_event=None,feed_sink=None):
    settings.validate()
    # The reference schedule is fixed in simulation time. Extend a short request
    # so every evaluation unit fits; never compress or silently truncate it.
    schedule=incidents(scenario,settings.duration_seconds,include_fault=False)
    scheduled_end=max([float(item["end_time"]) for item in schedule]+[0.0])
    settings.duration_seconds=max(settings.duration_seconds,scheduled_end)
    keys=settings.secrets(); node_ids=[f"node-{i}" for i in range(settings.node_count)]; nodes={}; ports={}; clock=SimulationClock(settings.speedup); process=None
    try:
        import psutil
        process=psutil.Process()
    except ImportError: pass
    for node_id in node_ids: nodes[node_id]=IDSNode(node_id,{peer:0 for peer in node_ids if peer!=node_id},keys,settings,clock,feed_sink)
    try:
        for i,(node_id,node) in enumerate(nodes.items()): ports[node_id]=await node.start(settings.base_port+i if settings.base_port else 0)
        for node in nodes.values(): node.peers.update(ports)
        for node in nodes.values(): node.runner=asyncio.create_task(node.run(),name=f"{node.id}-event-loop")
        warmup=await _warmup_mesh(nodes,ports,settings)
        clock.reset()
        simulation_started=time.perf_counter()
        events=generate(settings.seed,settings.node_count,scenario,settings.duration_seconds)
        offline_id=None
        topology_history=[]
        edge_states={}
        for i,a in enumerate(node_ids):
            for b in node_ids[i+1:]:
                state="reachable" if warmup.get((a,b))==warmup.get((b,a))=="reachable" else "unavailable"
                edge_states[(a,b)]=state; topology_history.append({"source":a,"target":b,"status":state,"start_time":0.0,"end_time":None})
        async def toggle_offline():
            offline_start=170.0; offline_end=180.0
            if not await _wait_until(clock,offline_start,stop_event): return
            await nodes[offline_id].close()
            for i,a in enumerate(node_ids):
                for b in node_ids[i+1:]:
                    if offline_id in (a,b):
                        row=next(x for x in reversed(topology_history) if (x["source"],x["target"])==(a,b) and x["end_time"] is None)
                        row["end_time"]=clock.now(); topology_history.append({"source":a,"target":b,"status":"offline","start_time":clock.now(),"end_time":None}); edge_states[(a,b)]="offline"
            if not await _wait_until(clock,offline_end,stop_event): return
            ports[offline_id]=await nodes[offline_id].start(ports[offline_id])
            for i,a in enumerate(node_ids):
                for b in node_ids[i+1:]:
                    if offline_id in (a,b):
                        row=next(x for x in reversed(topology_history) if (x["source"],x["target"])==(a,b) and x["end_time"] is None)
                        row["end_time"]=clock.now(); topology_history.append({"source":a,"target":b,"status":"reachable","start_time":clock.now(),"end_time":None}); edge_states[(a,b)]="reachable"
        offline_task=asyncio.create_task(toggle_offline()) if offline_id else None
        resource_samples=[]; resource_stop=asyncio.Event(); resource_task=None
        if process:
            process.cpu_percent(interval=None)
            resource_task=asyncio.create_task(_sample_rss(process,resource_stop,resource_samples))
        stopped=False
        for event in events:
            if not await _wait_until(clock,event.timestamp,stop_event): stopped=True; break
            await nodes[event.source_id].submit(event)
        await asyncio.gather(*(node.event_queue.join() for node in nodes.values()))
        fault_incident=None if stopped else await _inject_faults(settings,nodes,ports,keys,clock,scenario,stop_event)
        if fault_incident:
            settings.duration_seconds=max(settings.duration_seconds,float(fault_incident["end_time"]))
        if not stopped:
            await _wait_until(clock,settings.duration_seconds,stop_event)
        await asyncio.sleep(.05)
        await asyncio.gather(*(node.drain_trust_audits() for node in nodes.values()))
        if offline_task:
            await offline_task
        cpu=process.cpu_percent(interval=None) if process else None
        if resource_task:
            resource_stop.set(); await resource_task
        memory=sum(resource_samples)/len(resource_samples) if resource_samples else None
        peak_memory=max(resource_samples) if resource_samples else None
        truths=incidents(scenario,settings.duration_seconds,include_fault=False)
        all_decisions=[decision for node in nodes.values() for decision in node.decisions]
        local_decisions={node_id:node.local_decisions for node_id,node in nodes.items()}
        local_events={node_id:[event for observed in node.local_events.values() for event in observed] for node_id,node in nodes.items()}
        validated_alerts=[alert for node in nodes.values() for alert in node.incoming]
        evaluation=evaluate_incidents(truths,all_decisions,local_decisions,validated_alerts,node_ids,settings.grace_period_seconds,local_events)
        misleading_support=max((d.get("peer_weighted_support",0.0) for d in all_decisions if d.get("target_id")=="synthetic-fault-target"),default=0.0)
        tx_alerts=sum(node.transport.tx_alerts for node in nodes.values()); tx_frames=sum(node.transport.tx_frames for node in nodes.values()); rx_frames=sum(node.transport.rx_frames for node in nodes.values())
        tx_bytes=sum(node.transport.tx_bytes for node in nodes.values()); rx_bytes=sum(node.transport.rx_bytes for node in nodes.values()); validated_rx=len(validated_alerts); failed_sends=sum(node.transport.failed_sends for node in nodes.values())
        rejected_alerts={}
        for node in nodes.values():
            for reason,count in node.validator.rejections.items(): rejected_alerts[reason]=rejected_alerts.get(reason,0)+count
        unaccounted=max(0,tx_alerts-validated_rx-sum(rejected_alerts.values()))
        latencies=[row["latency_seconds"] for row in evaluation["latency_table"] if row["latency_seconds"] is not None]
        ops=operational(events=len(events),alerts_sent=tx_alerts,alerts_received=validated_rx,bytes_sent=tx_bytes,bytes_received=rx_bytes,avg_message_size=(tx_bytes/tx_frames if tx_frames else 0.0),latencies=latencies,cpu_percent=cpu,memory_bytes=memory,peak_memory_bytes=peak_memory,wall_runtime_seconds=time.perf_counter()-simulation_started)
        rejections={}; rejection_counts={}
        for node in nodes.values():
            for reason,count in node.validator.rejections.items():
                rejections[reason]=rejections.get(reason,0)+count; rejection_counts[reason]=rejection_counts.get(reason,0)+count
            for channel_reason,count in node.validator.peer_rejections.items(): rejections[f"{node.id}:{channel_reason[0]}:{channel_reason[1]}"]=count
            for channel_reason,count in node.transport.rejections.items():
                rejections[f"{node.id}:{channel_reason[0]}:{channel_reason[1]}"]=count
                reason=channel_reason[1]
                if reason not in {"schema","types_ranges","protocol","sender","signature","freshness","replay"}:
                    rejection_counts[reason]=rejection_counts.get(reason,0)+count
        delivery={"alerts_transmitted":tx_alerts,"validated_alerts_received":validated_rx,"rejected_by_reason":rejected_alerts,"failed_sends":failed_sends,"unaccounted":unaccounted}
        status={node_id:("stopped" if stopped else "online") for node_id in node_ids}
        for interval in topology_history:
            if interval["end_time"] is None: interval["end_time"]=clock.now()
        topology=[{"source":a,"target":b,"status":edge_states[(a,b)]} for i,a in enumerate(node_ids) for b in node_ids[i+1:]]
        trust_history=[{"observer_id":node.id,"peer_id":peer,**update} for node in nodes.values() for peer,state in node.trust.states.items() for update in state.history]
        feed=sorted([item for node in nodes.values() for item in node.feed],key=lambda x:x["simulation_time"])
        injected_watch_events=0
        return {"scenario":scenario,"seed":settings.seed,"duration_seconds":settings.duration_seconds,"grace_period_seconds":settings.grace_period_seconds,"correlation_window_seconds":settings.correlation_window,"rate_threshold":settings.rate_threshold,"reporting_threshold":settings.reporting_threshold,"decision_threshold":settings.min_peer_sources,"min_peer_sources":settings.min_peer_sources,"events":len(events)+injected_watch_events,"node_event_counts":{node.id:sum(len(observed) for observed in node.local_events.values()) for node in nodes.values()},"node_alert_counts":{node.id:len(node.local) for node in nodes.values()},"nodes":node_ids,"node_status":status,"ports":ports,"topology":topology,"topology_history":topology_history,"warmup":[{"source":a,"target":b,"status":state} for (a,b),state in warmup.items()],"alerts":sum(len(node.local) for node in nodes.values()),"messages_transmitted":tx_frames,"failed_sends":failed_sends,"received":validated_rx,"messages_received":rx_frames,"alert_delivery":delivery,"decisions":len(all_decisions),"incidents":truths,"decision_table":evaluation["decision_table"],"latency_table":evaluation["latency_table"],"classification":evaluation["classification"],"classification_std":evaluation["classification_std"],"per_node_classification":evaluation["per_node_classification"],"operational":ops,"fault_scenario":scenario in ("all","invalid_message"),"rejections":rejections,"rejection_counts":rejection_counts,"feed":feed,"stopped":stopped}
    finally:
        await asyncio.gather(*(node.stop() for node in nodes.values()),return_exceptions=True)
        await asyncio.gather(*(node.close() for node in nodes.values()),return_exceptions=True)

def main():
    parser=argparse.ArgumentParser(description="localhost-only synthetic collaborative IDS simulation")
    parser.add_argument("--seed",type=int,default=7); parser.add_argument("--speedup",type=float,default=100); parser.add_argument("--port",type=int,default=0); parser.add_argument("--scenario",choices=("all",)+SCENARIOS,default="all"); parser.add_argument("--duration",type=float,default=120); args=parser.parse_args()
    settings=Settings(seed=args.seed,speedup=args.speedup,base_port=args.port,duration_seconds=args.duration)
    if False: result={}
    else: result=asyncio.run(run(settings,args.scenario))
    print(json.dumps(result,indent=2))
if __name__=="__main__": main()
