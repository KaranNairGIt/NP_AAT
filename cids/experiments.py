"""Five-seed (configurable) experiment runner with raw and summary exports."""
import asyncio,csv,json,statistics
import argparse
from pathlib import Path
from .simulation import run
from .config import Settings

METRICS=("tp","tn","fp","fn","precision","recall","f1","accuracy","false_positive_rate")
def summarize_runs(runs):
    output=[]
    methods=sorted({m for item in runs for m in item["classification"]})
    for method in methods:
        method_metrics=tuple(m for m in METRICS if m not in ("tp","tn","fp","fn")) if method=="local_only_per_node_average" else METRICS
        for metric in method_metrics:
            values=[float(item["classification"][method][metric]) for item in runs if method in item["classification"]]
            mean=statistics.mean(values) if values else 0.0; std=statistics.stdev(values) if len(values)>1 else 0.0
            output.append({"method":method,"metric":metric,"mean":mean,"std":std,"mean_plus_minus_std":f"{mean:.4f} ± {std:.4f}"})
    return output

async def run_experiments(seeds=None,*,count=5,start_seed=7,out="results",scenario="all",nodes=4,settings_options=None,stop_event=None):
    if seeds is None: seeds=[start_seed+10*i for i in range(count)]
    destination=Path(out); destination.mkdir(parents=True,exist_ok=True); options=dict(settings_options or {}); runs=[]
    for seed in seeds:
        if stop_event is not None and stop_event.is_set(): break
        settings=Settings(node_count=nodes,seed=seed,**options)
        runs.append(await run(settings,scenario,stop_event=stop_event))
    summary=summarize_runs(runs)
    (destination/"experiment.json").write_text(json.dumps({"runs":runs,"summary":summary},indent=2),encoding="utf-8")
    raw=[]; latency=[]; decisions=[]
    for item in runs:
        for method,metrics in item["classification"].items(): raw.append({"seed":item["seed"],"scenario":scenario,"method":method,**metrics})
        latency.extend({"seed":item["seed"],**row} for row in item["latency_table"])
        decisions.extend({"seed":item["seed"],**row} for row in item["decision_table"])
    def write_csv(filename,rows):
        if not rows: return
        with (destination/filename).open("w",newline="",encoding="utf-8") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    write_csv("experiment.csv",raw); write_csv("experiment_summary.csv",summary); write_csv("incident_latency.csv",latency); write_csv("incident_decisions.csv",decisions)
    return {"runs":runs,"summary":summary,"count":len(runs)}

async def run_seeds(seeds,out="results"): return await run_experiments(seeds=seeds,out=out)

async def run_threshold_sweep(*,seeds=None,count=5,start_seed=7,thresholds=None,min_peer_sources=None,out="results",scenario="all",nodes=4,settings_options=None,stop_event=None):
    """Run an unmodified parameter grid and export collaborative F1/FPR mean±std."""
    seeds=list(seeds or [start_seed+10*i for i in range(count)])
    thresholds=list(thresholds or [round(.3+i*.1,1) for i in range(7)])
    source_counts=list(min_peer_sources or [1,2,3])
    options=dict(settings_options or {}); rows=[]
    for threshold in thresholds:
        for source_count in source_counts:
            if source_count>nodes-1: continue
            observed=[]
            for seed in seeds:
                if stop_event is not None and stop_event.is_set(): break
                settings=Settings(node_count=nodes,seed=seed,quorum_weight=float(threshold),min_peer_sources=int(source_count),**options)
                if stop_event is None: observed.append(await run(settings,scenario))
                else: observed.append(await run(settings,scenario,stop_event=stop_event))
            if not observed: continue
            f1=[r["classification"]["collaborative"]["f1"] for r in observed]
            fpr=[r["classification"]["collaborative"]["false_positive_rate"] for r in observed]
            f1_mean=statistics.mean(f1); fpr_mean=statistics.mean(fpr)
            rows.append({"decision_threshold":threshold,"min_peer_sources":source_count,"seed_count":len(observed),
                "collaborative_f1_mean":f1_mean,"collaborative_f1_std":statistics.stdev(f1) if len(f1)>1 else 0.0,
                "collaborative_fpr_mean":fpr_mean,"collaborative_fpr_std":statistics.stdev(fpr) if len(fpr)>1 else 0.0,
                "misleading_peer_weighted_support_mean":statistics.mean([r.get("misleading_peer_weighted_support",0.0) for r in observed])})
    destination=Path(out); destination.mkdir(parents=True,exist_ok=True)
    if rows:
        with (destination/"threshold_sweep.csv").open("w",newline="",encoding="utf-8") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    (destination/"threshold_sweep.json").write_text(json.dumps({"seeds":seeds,"rows":rows},indent=2),encoding="utf-8")
    return {"seeds":seeds,"rows":rows,"count":len(rows)}

def main():
    parser=argparse.ArgumentParser(description="CIDS multi-seed and threshold-sweep experiments")
    parser.add_argument("--threshold-sweep",action="store_true"); parser.add_argument("--scenario",default="all"); parser.add_argument("--nodes",type=int,default=4); parser.add_argument("--seeds",type=int,default=5); parser.add_argument("--seed",type=int,default=7); parser.add_argument("--speedup",type=float,default=500)
    parser.add_argument("--out",default="results",help="Directory for JSON and CSV experiment exports")
    args=parser.parse_args()
    if args.threshold_sweep:
        result=asyncio.run(run_threshold_sweep(count=args.seeds,start_seed=args.seed,scenario=args.scenario,nodes=args.nodes,settings_options={"speedup":args.speedup},out=args.out))
    else:
        result=asyncio.run(run_experiments(count=args.seeds,start_seed=args.seed,scenario=args.scenario,nodes=args.nodes,settings_options={"speedup":args.speedup},out=args.out))
    print(json.dumps({k:v for k,v in result.items() if k!="runs"},indent=2))

if __name__=="__main__": main()
