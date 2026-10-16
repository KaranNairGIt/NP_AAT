import asyncio

from cids.baselines import majority_peer_vote
from cids.clock import SimulationClock
from cids.config import Settings
from cids.evaluation import evaluate_incidents
from cids.event_generator import generate, incidents
from cids.event_generator import REFERENCE_DURATION
from cids.event_generator import REQUIRED_DURATION
from cids.experiments import summarize_runs
from cids.metrics import classification
from cids.models import Alert, Event
from cids.node import IDSNode
from cids.message_security import sign
from cids.simulation import run
from cids.consensus_engine import ConsensusEngine
from cids import experiments
from ui.charts import trust_history_frame,topology_initial_time,metric_frame,METHOD_COLORS


def test_latency_is_measured_from_each_incident_start():
    truth = [{"incident_id":"i1", "target_id":"host", "event_type":"login", "start_time":10, "end_time":11, "is_attack":True}]
    evaluated = evaluate_incidents(truth, [{"target_id":"host", "event_type":"login", "timestamp":13, "is_attack":True, "weighted_support":1, "sources":["n0"]}], {}, [], ["n0"], grace=5)
    assert evaluated["latency_table"][0]["latency_seconds"] == 3


def test_forged_claim_does_not_change_honest_peers_trust():
    async def case():
        settings = Settings(node_count=2)
        keys = {"node-0":b"0"*32, "node-1":b"1"*32}
        node = IDSNode("node-1", {"node-0":0}, keys, settings, SimulationClock())
        forged = Alert(1,"forged","e1","node-0",0,"login_fail","host",4,.9,"forged evidence", "0"*64)
        before = node.trust.get("node-0")
        await node.handle("node-0", __import__("json").dumps(forged.__dict__).encode())
        assert node.trust.get("node-0") == before
        assert node.validator.rejections["signature"] == 1
        assert node.transport.rejections[("node-0", "signature")] == 1
    asyncio.run(case())


def test_trust_uses_each_observers_own_authenticated_evidence():
    async def case():
        keys = {"node-0":b"0"*32,"node-1":b"1"*32,"node-2":b"2"*32}
        observers = [IDSNode(f"node-{i}", {f"node-{j}":0 for j in range(3) if i != j}, keys, Settings(node_count=3), SimulationClock()) for i in (1,2)]
        event = Event("local", 0, "node-1", "host", "login_fail", {})
        observers[0].local_events[("host","login_fail")].append(event)
        alert = Alert(1,"a1","e1","node-0",0,"login_fail","host",4,.9,"authenticated report")
        sign(alert,keys["node-0"])
        for observer in observers:
            await observer.handle("node-0", __import__("json").dumps(alert.__dict__).encode())
        assert observers[0].trust.get("node-0") == .55
        assert observers[1].trust.get("node-0") == .5
    asyncio.run(case())


def test_majority_vote_counts_distinct_validated_alert_sources():
    incident = {"target_id":"host","event_type":"probe","start_time":1,"end_time":2}
    alerts = [Alert(1,f"a{i}",f"e{i}",f"node-{i}",1.5,"probe","host",4,.9,"valid") for i in range(3)]
    assert not majority_peer_vote(incident, alerts[:1], [f"node-{i}" for i in range(4)], 1)["decision"]
    assert majority_peer_vote(incident, alerts[:3], [f"node-{i}" for i in range(4)], 1)["decision"]
    local = {"node-0":[{"target_id":"host","event_type":"probe","timestamp":1.5}]}
    score = evaluate_incidents([dict(incident,incident_id="i",is_attack=True)], [], local, alerts[:1], [f"node-{i}" for i in range(4)], 1)
    row = score["decision_table"][0]
    assert row["local_only_any"] is True and row["majority_vote"] is False


def test_collaborative_and_majority_baseline_are_not_identical_when_peer_quorum_is_met():
    incident={"incident_id":"i","target_id":"host","event_type":"probe","start_time":1,"end_time":2,"is_attack":True}
    peers=[Alert(1,f"a{i}",f"e{i}",f"node-{i}",1.5,"probe","host",4,.8,"validated") for i in (0,1)]
    result=evaluate_incidents([incident],[{"target_id":"host","event_type":"probe","timestamp":1.5,"is_attack":True,"weighted_support":1.6,"peer_weighted_support":1.6,"sources":["node-0","node-1"],"peer_sources":["node-0","node-1"]}],{},peers,[f"node-{i}" for i in range(4)],0)
    row=result["decision_table"][0]
    assert row["collaborative"] and not row["local_only_any"]
    assert not row["majority_vote"]


def test_incident_record_explains_local_decision_and_keeps_self_support():
    incident={"incident_id":"i","target_id":"host","event_type":"probe","start_time":1,"end_time":2,"is_attack":True}
    decision={"target_id":"host","event_type":"probe","timestamp":1.5,"is_attack":True,"weighted_support":1.8,"peer_weighted_support":.8,"decision_threshold":.5,"sources":["node-0","node-1"],"peer_sources":["node-1"],"explanation":"local detector crossed threshold"}
    local={"node-0":[{"target_id":"host","event_type":"probe","timestamp":1.5}]}
    row=evaluate_incidents([incident],[decision],local,[],["node-0","node-1"],0)["decision_table"][0]
    assert row["weighted_support"]==1.8
    assert row["local_detection_nodes"]=="node-0"
    assert row["decision_path"]=="own local detection by node-0"


def test_incident_records_match_csv_and_json_exports(tmp_path,monkeypatch):
    import csv,json
    record={"incident_id":"inc-test","is_attack":True,"collaborative":True,"weighted_support":.8,"distinct_sources":2,"decision_path":"peer evidence"}
    metrics={"tp":1,"tn":0,"fp":0,"fn":0,"precision":1.,"recall":1.,"f1":1.,"accuracy":1.,"false_positive_rate":0.}
    async def fake_run(settings,scenario,**kwargs):
        return {"seed":settings.seed,"classification":{"collaborative":metrics},"decision_table":[record],"latency_table":[]}
    monkeypatch.setattr(experiments,"run",fake_run)
    async def case():
        await experiments.run_experiments(seeds=[7],out=tmp_path)
    asyncio.run(case())
    exported=json.loads((tmp_path/"experiment.json").read_text(encoding="utf-8"))["runs"][0]["decision_table"][0]
    with (tmp_path/"incident_decisions.csv").open(encoding="utf-8",newline="") as handle: csv_record=next(csv.DictReader(handle))
    assert exported==record
    for key,value in record.items(): assert str(value)==csv_record[key]


def test_ground_truth_has_benign_evaluation_units_and_confusion_counts_reconcile():
    truth = incidents("all", include_fault=True)
    assert any(not row["is_attack"] for row in truth)
    assert any(row["incident_id"] == "inc-false-peer-alert" for row in truth)
    assert any(row["incident_id"] == "inc-duplicate-delayed" for row in truth)
    result = evaluate_incidents(truth, [], {}, [], ["node-0","node-1"], grace=5)
    for method, metrics in result["classification"].items():
        if method=="local_only_per_node_average":
            assert not {"tp","tn","fp","fn"} & set(metrics)
        else:
            assert len(result["decision_table"]) == metrics["tp"] + metrics["tn"] + metrics["fp"] + metrics["fn"]
    low = next(row for row in truth if row["incident_id"] == "inc-lowrate")
    assert low["end_time"] - low["start_time"] == 60


def test_low_rate_has_three_subthreshold_observations_within_reporting_window():
    events = generate(7, 4, "low_rate", REFERENCE_DURATION)
    assert len(events) == 12
    for node in {e.source_id for e in events}:
        local = [e for e in events if e.source_id == node]
        assert len(local) == 3 and local[-1].timestamp-local[0].timestamp < 10
        assert len(local) < Settings().rate_threshold


def test_visibility_and_event_distribution_scale_from_four_through_ten_nodes():
    for count in range(4, 11):
        events=generate(11,count,"all")
        distribution={f"node-{i}":sum(e.source_id==f"node-{i}" for e in events) for i in range(count)}
        average=sum(distribution.values())/count
        assert min(distribution.values()) >= .65*average, (count,distribution)
        assert max(distribution.values()) <= 1.50*average, (count,distribution)
        for incident_id,required in (("inc-concentrated",1),("inc-coordinated",3),("inc-lowrate",3),
                                     ("inc-misleading",3),("inc-offline",3),("inc-replay",3),("inc-invalid",3)):
            observers={e.source_id for e in events if e.incident_id==incident_id}
            assert len(observers)>=required, (count,incident_id,distribution)
        misleading={e.source_id for e in events if e.incident_id=="inc-misleading"}
        assert "node-0" not in misleading


def test_reference_configuration_matches_settings_baseline():
    import json
    from pathlib import Path
    reference=json.loads((Path(__file__).parents[1]/"configs"/"reference.json").read_text(encoding="utf-8"))
    settings=Settings()
    assert reference["nodes"]==settings.node_count==4
    assert reference["duration_seconds"]==settings.duration_seconds==REFERENCE_DURATION
    assert reference["rate_threshold"]==settings.rate_threshold
    assert reference["decision_threshold"]==settings.quorum_weight
    assert reference["min_peer_sources"]==settings.min_peer_sources


def test_trust_chart_includes_initial_value_and_single_step():
    history=[{"observer_id":"node-0","peer_id":"node-1","simulation_time":4.0,"to":.55}]
    frame=trust_history_frame(history,["node-0","node-1","node-2"],"node-0")
    peer=frame[frame.peer_id=="node-1"]
    assert list(peer.simulation_time)==[0.,4.]
    assert list(peer["to"])==[.5,.55]
    assert list(frame[frame.peer_id=="node-2"]["to"])==[.5]


def test_topology_slider_defaults_to_first_offline_fault():
    assert topology_initial_time({"incidents":[{"incident_id":"inc-offline","start_time":170}]})==170
    assert topology_initial_time({"incidents":[]})==0


def test_dashboard_metric_labels_theme_and_method_colors_are_consistent():
    from pathlib import Path
    root=Path(__file__).parents[1]
    frame=metric_frame({"classification":{"collaborative":{"tp":2,"tn":1,"fp":0,"fn":1,"precision":1.,"recall":.667,"f1":.8,"accuracy":.75,"false_positive_rate":0.}}})
    assert "True positives" in frame.columns and "False positive rate" in frame.columns
    assert "tp" not in frame.columns
    assert 'base = "light"' in (root/".streamlit"/"config.toml").read_text(encoding="utf-8")
    assert "streamlit==1.66.0" in (root/"requirements.txt").read_text(encoding="utf-8")
    assert METHOD_COLORS=={"collaborative":"#2563EB","local_only_any":"#64748B","local_only_per_node_average":"#94A3B8","majority_vote":"#D97706","majority_vote_observers":"#7C3AED"}


def test_incident_windows_are_fixed_and_short_all_run_is_extended():
    regular=incidents("all",180,include_fault=True)
    long=incidents("all",390,include_fault=True)
    assert regular==long
    assert max(i["end_time"] for i in regular)<=REQUIRED_DURATION
    async def case():
        result=await run(Settings(node_count=4,duration_seconds=30,speedup=500),"all")
        assert result["duration_seconds"]>=REQUIRED_DURATION
        assert max(i["end_time"] for i in result["incidents"])<=result["duration_seconds"]
    asyncio.run(case())


def test_suspicion_alert_does_not_count_toward_either_majority_baseline():
    from cids.baselines import majority_vote_observers
    incident={"target_id":"host","event_type":"probe","start_time":1,"end_time":2}
    suspicion=Alert(1,"s","e","node-0",1.5,"probe","host",2,.5,"sub-threshold")
    nodes=[f"node-{i}" for i in range(4)]
    local={n:[Event(n,1.5,n,"host","probe",{})] for n in nodes}
    assert not majority_peer_vote(incident,[suspicion],nodes,1)["decision"]
    assert not majority_vote_observers(incident,[suspicion],local,nodes,1)["decision"]


def test_eight_node_alert_delivery_fans_out_concurrently():
    import time
    async def case():
        keys={f"node-{i}":bytes([i])*32 for i in range(8)}
        node=IDSNode("node-0",{f"node-{i}":9000+i for i in range(8)},keys,Settings(node_count=8),SimulationClock())
        received=[]
        async def fake_send(port,sender,payload):
            await asyncio.sleep(.03)
            received.append((port,time.perf_counter()))
        node.transport.send=fake_send
        event=Event("fanout",1,"node-0","host","login_fail",{})
        await node.publish(event,{"decision":True,"score":1,"explanation":"test"})
        assert len(received)==7
        assert max(t for _,t in received)-min(t for _,t in received)<.02
    asyncio.run(case())


def test_false_positive_rate_is_reported():
    assert classification([True,False],[True,True])["false_positive_rate"] == 1


def test_multi_seed_summary_reports_mean_and_sample_std():
    runs = [{"classification":{"m":{"tp":i,"tn":0,"fp":0,"fn":0,"precision":i,"recall":0,"f1":0,"accuracy":0,"false_positive_rate":0}}} for i in (1,3)]
    row = next(r for r in summarize_runs(runs) if r["method"] == "m" and r["metric"] == "tp")
    assert row["mean"] == 2 and row["std"] == 2**.5


def test_simulation_evaluates_duplicate_alert_unit_once_and_reconciles_delivery():
    async def case():
        result = await run(Settings(node_count=4, speedup=500), "all")
        ids = [row["incident_id"] for row in result["incidents"]]
        assert ids.count("inc-false-peer-alert") == 1
        delivery = result["alert_delivery"]
        assert delivery["unaccounted"] == 0
        assert delivery["alerts_transmitted"] == delivery["validated_alerts_received"] + sum(delivery["rejected_by_reason"].values())
        assert result["operational"]["bytes_received"] > 0
        assert sum(result["node_event_counts"].values())==result["events"]
        assert {"empty_frame","truncated","oversized_frame","non_utf8","invalid_json"} <= set(result["rejection_counts"])
        assert all(x["delta"]>=0 or x["reason"]=="authenticated_alert_uncorroborated_while_target_observed" for x in result["trust_history"])
        assert any(x["observer_id"]=="node-1" and x["peer_id"]=="node-0" and x["delta"]<0 for x in result["trust_history"])
        false_peer=next(x for x in result["decision_table"] if x["incident_id"]=="inc-false-peer-alert")
        assert not false_peer["collaborative"]
        assert all(not x["local_only_any"] or x["collaborative"] for x in result["decision_table"])
    asyncio.run(case())


def test_peer_quorum_requires_two_sources_but_local_detection_overrides_it():
    engine=ConsensusEngine(threshold=.5,min_peer_sources=2)
    alert=Alert(1,"a","e","node-0",1,"probe","host",3,.8,"evidence")
    one=[(1,alert,.8)]
    assert not engine.decide(("host","probe"),one,2,observer_id="node-1")["is_attack"]
    assert engine.decide(("host","probe"),one,2,observer_id="node-0",local_detected=True)["is_attack"]


def test_subthreshold_suspicion_confidence_tracks_local_score():
    async def case():
        settings=Settings(node_count=2); keys={"node-0":b"0"*32,"node-1":b"1"*32}; node=IDSNode("node-0",{},keys,settings,SimulationClock())
        events=[Event(str(i),float(i),"node-0","host","login_fail",{}) for i in (1,2,3)]
        result=None
        for event in events: result=node.detector.observe(event)
        await node.publish(events[-1],result)
        assert not result["decision"] and result["score"]==.5
        assert node.local[-1].confidence==.5 and node.local[-1].severity==2
    asyncio.run(case())


def test_per_node_average_averages_metrics_and_reports_cross_node_std():
    truth=[True,False]
    local={"node-0":[{"target_id":"a","event_type":"probe","timestamp":1}],
           "node-1":[{"target_id":"b","event_type":"probe","timestamp":1}]}
    incidents_=[{"incident_id":"a","target_id":"a","event_type":"probe","start_time":0,"end_time":2,"is_attack":True},
                {"incident_id":"b","target_id":"b","event_type":"probe","start_time":0,"end_time":2,"is_attack":False}]
    result=evaluate_incidents(incidents_,[],local,[],["node-0","node-1"],0)
    avg=result["classification"]["local_only_per_node_average"]
    assert avg["precision"] == .5
    assert avg["f1"] == .5
    assert not {"tp","tn","fp","fn"} & set(avg)
    assert result["classification_std"]["local_only_per_node_average"]["precision"] > .7


def test_observer_majority_can_detect_when_all_node_majority_cannot():
    incident={"incident_id":"i","target_id":"host","event_type":"probe","start_time":1,"end_time":2,"is_attack":True}
    alert=Alert(1,"a","e","node-0",1.5,"probe","host",3,.8,"validated")
    event=Event("e",1.5,"node-0","host","probe",{})
    result=evaluate_incidents([incident],[],{},[alert],[f"node-{i}" for i in range(4)],0,
                              {"node-0":[event],"node-1":[],"node-2":[],"node-3":[]})
    row=result["decision_table"][0]
    assert row["majority_vote"] is False
    assert row["majority_vote_observers"] is True


def test_authenticated_unconfirmed_alert_decreases_trust_after_window():
    async def case():
        settings=Settings(node_count=2,correlation_window=1,speedup=1000)
        keys={"node-0":b"0"*32,"node-1":b"1"*32}; clock=SimulationClock(settings.speedup)
        node=IDSNode("node-1",{"node-0":0},keys,settings,clock)
        now=clock.now(); node.local_events[("host","benign_observation")].append(Event("watch",now,"node-1","host","benign_observation",{}))
        alert=Alert(1,"auth-false","e1","node-0",now,"probe","host",3,.8,"authenticated report"); sign(alert,keys["node-0"])
        await node.handle("node-0",__import__("json").dumps(alert.__dict__).encode())
        await node.drain_trust_audits()
        assert node.trust.get("node-0")==.4
        update=node.trust.states["node-0"].history[-1]
        assert update["reason"]=="authenticated_alert_uncorroborated_while_target_observed"
        assert "no independent probe observation" in update["evidence"]
    asyncio.run(case())


def test_replay_does_not_change_sender_trust():
    async def case():
        settings=Settings(node_count=2); keys={"node-0":b"0"*32,"node-1":b"1"*32}; node=IDSNode("node-1",{"node-0":0},keys,settings,SimulationClock())
        now=node.clock.now(); alert=Alert(1,"repeat","e1","node-0",now,"probe","host",3,.8,"report"); sign(alert,keys["node-0"]); payload=__import__("json").dumps(alert.__dict__).encode()
        await node.handle("node-0",payload); before=node.trust.get("node-0"); await node.handle("node-0",payload)
        assert node.trust.get("node-0")==before==.5
        assert node.validator.rejections["replay"]==1
    asyncio.run(case())


def test_e2e_self_detection_and_lowrate_collaboration():
    async def case():
        concentrated=await run(Settings(node_count=4,speedup=100),"concentrated")
        concentrated_row=next(x for x in concentrated["decision_table"] if x["incident_id"]=="inc-concentrated")
        assert concentrated_row["local_only_any"] and concentrated_row["collaborative"]
        assert all(item["status"]=="reachable" for item in concentrated["warmup"])
        lowrate=await run(Settings(node_count=4,speedup=100),"low_rate")
        row=next(x for x in lowrate["decision_table"] if x["incident_id"]=="inc-lowrate")
        assert row["collaborative"] and not row["local_only_any"]
    asyncio.run(case())


def test_offline_peer_topology_is_timed_and_recovers():
    async def case():
        result=await run(Settings(node_count=4,speedup=100),"offline_peer")
        edge=next(x for x in result["topology_history"] if x["target"]=="node-3" and x["status"]=="offline")
        assert edge["start_time"]<=172 and edge["end_time"]>=180
        assert any(x["target"]=="node-3" and x["status"]=="reachable" and abs(x["start_time"]-edge["end_time"])<.01 for x in result["topology_history"])
    asyncio.run(case())


def test_threshold_sweep_writes_f1_and_fpr_for_each_setting(tmp_path,monkeypatch):
    async def fake_run(settings,scenario):
        return {"classification":{"collaborative":{"f1":settings.quorum_weight,"false_positive_rate":settings.min_peer_sources/10}},"misleading_peer_weighted_support":.6}
    monkeypatch.setattr(experiments,"run",fake_run)
    async def case():
        result=await experiments.run_threshold_sweep(seeds=[7,17],thresholds=[.4,.6],min_peer_sources=[1,2],out=tmp_path,nodes=4)
        assert result["count"]==4
        rows=result["rows"]
        assert rows[0]["collaborative_f1_mean"]==.4 and rows[0]["collaborative_fpr_mean"]==.1
        assert (tmp_path/"threshold_sweep.csv").exists()
    asyncio.run(case())
