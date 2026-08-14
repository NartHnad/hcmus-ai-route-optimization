from __future__ import annotations
import argparse, csv, math, random, statistics, sys, time, tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.data.data_loader import load_dataset, get_json_datasets
from src.models.models import Graph, SearchResult

def _try_import(func_name, module_path):
    try:
        mod = __import__(module_path, fromlist=[func_name])
        return getattr(mod, func_name)
    except Exception as exc:
        print(f"[IMPORT WARN] {func_name} from {module_path}: {exc}")
        return None

_bfs_fn   = _try_import("bfs",                "src.algorithms.bfs")
_dfs_fn   = _try_import("dfs",                "src.algorithms.dfs")
_ucs_fn   = _try_import("ucs",                "src.algorithms.ucs")
_astar_fn = _try_import("a_star",             "src.algorithms.a_star")
_beam_fn  = _try_import("beam_search",        "src.algorithms.beam_search")
_ga_fn    = _try_import("genetic_algorithm",  "src.algorithms.genetic_algorithm")
_sa_fn    = _try_import("simulated_annealing","src.algorithms.simulated_annealing")

DEFAULT_DATASET    = "map_district_1.json"
DETERMINISTIC_RUNS = 10
STOCHASTIC_RUNS    = 30
WARMUP_RUNS        = 2
BEAM_WIDTH         = 10
GA_POPULATION_SIZE = 50
GA_GENERATIONS     = 100
GA_MUTATION_RATE   = 0.2
SA_INITIAL_TEMP    = 1000.0
SA_DECAY_RATE      = 0.995
STOCHASTIC_SEEDS   = list(range(STOCHASTIC_RUNS))

SCENARIO_DEFINITIONS = [
    {"name": "S1_Short",  "hop_pct": (0.0,  0.15), "description": "Short route"},
    {"name": "S2_Medium", "hop_pct": (0.25, 0.45), "description": "Medium route"},
    {"name": "S3_Long",   "hop_pct": (0.55, 0.80), "description": "Long route"},
]
MULTI_LOCATION_SIZES = [3, 5, 8]

@dataclass
class RawRecord:
    algorithm: str; group: str; scenario: str; run: int; seed: Optional[int]
    success: bool; time_ms: float; path_length: int; total_cost: float
    distance_km: float; visited_nodes: int; expanded_nodes: int
    peak_memory_kb: float; error_type: str = ""; error_msg: str = ""

@dataclass
class FindingRecord:
    algorithm: str; file: str; function: str; scenario: str
    observed: str; expected: str; possible_cause: str

def load_graph(name):
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        g = load_dataset(name)
    return g

def get_all_node_ids(g): return list(g.nodes.keys())

def canonical_route_cost(graph, path):
    tc = 0.0; td = 0.0
    for i in range(len(path)-1):
        e = graph.get_edge(path[i], path[i+1])
        if e is None: return float("inf"), float("inf")
        tc += e.calculate_cost(); td += e.distance
    return tc, td

def validate_single_route(graph, path, start_id, goal_id):
    if not path: return False, "path is empty"
    if path[0] != start_id: return False, f"starts at {path[0]!r}"
    if path[-1] != goal_id: return False, f"ends at {path[-1]!r}"
    for n in path:
        if n not in graph.nodes: return False, f"node {n!r} missing"
    for i in range(len(path)-1):
        if graph.get_edge(path[i], path[i+1]) is None:
            return False, f"no edge {path[i]!r}->{path[i+1]!r}"
    return True, ""

def validate_multi_route(graph, path, start_id, goal_ids):
    if not path: return False, "path is empty"
    if path[0] != start_id: return False, f"starts at {path[0]!r}"
    ps = set(path)
    for g in goal_ids:
        if g not in ps: return False, f"goal {g!r} not visited"
    for n in path:
        if n not in graph.nodes: return False, f"node {n!r} missing"
    return True, ""

def _bfs_hop_distance(graph, start_id):
    from collections import deque
    dist = {start_id: 0}; q = deque([start_id])
    while q:
        node = q.popleft()
        for edge in graph.get_neighbors(node):
            nbr = edge.to_node
            if nbr not in dist:
                dist[nbr] = dist[node]+1; q.append(nbr)
    return dist

def select_scenario_nodes(graph, hop_pct_range, rng):
    node_ids = get_all_node_ids(graph)
    if len(node_ids) < 2: return None
    lo_pct, hi_pct = hop_pct_range
    candidates = []
    for start in rng.sample(node_ids, min(20, len(node_ids))):
        hd = _bfs_hop_distance(graph, start)
        if len(hd) < 2: continue
        mx = max(hd.values())
        if mx == 0: continue
        lo = max(1, int(lo_pct*mx)); hi = max(lo, int(hi_pct*mx))
        eligible = [n for n,d in hd.items() if lo<=d<=hi]
        if eligible:
            g = rng.choice(eligible)
            candidates.append((start, g, hd[g]))
    if not candidates: return None
    candidates.sort(key=lambda x: x[2])
    s, g, _ = candidates[len(candidates)//2]
    return s, g

def select_multi_location_nodes(graph, n_goals, rng):
    node_ids = get_all_node_ids(graph)
    if len(node_ids) < n_goals+1: return None
    for _ in range(30):
        start = rng.choice(node_ids)
        hd = _bfs_hop_distance(graph, start)
        reachable = [n for n in hd if n!=start]
        if len(reachable) >= n_goals:
            return start, rng.sample(reachable, n_goals)
    return None

def measure_peak_memory_kb(fn, *args, **kwargs):
    tracemalloc.start()
    try: result = fn(*args, **kwargs)
    finally: _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    return result, peak/1024.0

def count_expanded_nodes(result):
    try:
        from src.constants import StepType
        return sum(1 for s in result.steps if hasattr(s,"step_type") and s.step_type==StepType.EXPAND)
    except: return 0

class AlgorithmAdapter:
    @staticmethod
    def run_bfs(graph, start, goal, seed=None): return _bfs_fn(graph, start, goal)
    @staticmethod
    def run_dfs(graph, start, goal, seed=None): return _dfs_fn(graph, start, goal)
    @staticmethod
    def run_ucs(graph, start, goal, seed=None): return _ucs_fn(graph, start, goal)
    @staticmethod
    def run_astar(graph, start, goal, seed=None): return _astar_fn(graph, start, goal)
    @staticmethod
    def run_beam(graph, start, goal, seed=None):
        return _beam_fn(graph, start, goal, beam_width=BEAM_WIDTH)
    @staticmethod
    def run_ga(graph, start, goal, seed=None):
        if seed is not None: random.seed(seed)
        return _ga_fn(graph, start, goal, population_size=GA_POPULATION_SIZE,
                      generations=GA_GENERATIONS, mutation_rate=GA_MUTATION_RATE)
    @staticmethod
    def run_sa(graph, start, goals, seed=None):
        if seed is not None: random.seed(seed)
        return _sa_fn(graph, start, goals, respect_goal_order=False,
                      initial_temp=SA_INITIAL_TEMP, decay_rate=SA_DECAY_RATE)

SEARCH_ALGORITHMS = [
    ("BFS",         AlgorithmAdapter.run_bfs,   "search",       False, _bfs_fn   is not None),
    ("DFS",         AlgorithmAdapter.run_dfs,   "search",       False, _dfs_fn   is not None),
    ("UCS",         AlgorithmAdapter.run_ucs,   "search",       False, _ucs_fn   is not None),
    ("A*",          AlgorithmAdapter.run_astar, "search",       False, _astar_fn is not None),
    ("BeamSearch",  AlgorithmAdapter.run_beam,  "search",       False, _beam_fn  is not None),
    ("GeneticAlgo", AlgorithmAdapter.run_ga,    "search",       True,  _ga_fn    is not None),
]
OPTIMIZATION_ALGORITHMS = [
    ("SimulatedAnnealing", AlgorithmAdapter.run_sa, "optimization", True, _sa_fn is not None),
]

def run_single_benchmark(algo_name, adapter_fn, graph, start, goal_or_goals,
                         run_idx, seed, scenario_name, group, is_multi=False):
    rec = RawRecord(algorithm=algo_name, group=group, scenario=scenario_name, run=run_idx,
                    seed=seed, success=False, time_ms=0.0, path_length=0, total_cost=0.0,
                    distance_km=0.0, visited_nodes=0, expanded_nodes=0, peak_memory_kb=0.0)
    try:
        t_start = time.perf_counter()
        result = adapter_fn(graph, start, goal_or_goals, seed=seed)
        rec.time_ms = (time.perf_counter()-t_start)*1000.0
        try:
            _, pk = measure_peak_memory_kb(adapter_fn, graph, start, goal_or_goals, seed=seed)
            rec.peak_memory_kb = pk
        except: rec.peak_memory_kb = -1.0
        rec.expanded_nodes = count_expanded_nodes(result)
        rec.visited_nodes  = len(result.visited_order) if result.visited_order else 0
        if is_multi:
            is_valid, reason = validate_multi_route(graph, result.path, start, goal_or_goals)
        else:
            is_valid, reason = validate_single_route(graph, result.path, start, goal_or_goals)
        if result.success and is_valid:
            cost, dist = canonical_route_cost(graph, result.path)
            rec.success=True; rec.path_length=len(result.path); rec.total_cost=cost; rec.distance_km=dist
        else:
            rec.error_msg = reason if reason else result.message
    except Exception as exc:
        rec.error_type = type(exc).__name__; rec.error_msg = str(exc)[:300]
    return rec

def warmup(adapter_fn, graph, start, goal_or_goals, is_multi=False):
    for _ in range(WARMUP_RUNS):
        try: adapter_fn(graph, start, goal_or_goals, seed=0 if is_multi else None)
        except: pass

def build_point_to_point_scenarios(graph, seed=42):
    rng = random.Random(seed); scenarios = []
    for sdef in SCENARIO_DEFINITIONS:
        pair = select_scenario_nodes(graph, sdef["hop_pct"], rng)
        if pair is None: print(f"[WARN] Could not build {sdef['name']}"); continue
        s, g = pair
        scenarios.append({"name": sdef["name"], "description": sdef["description"], "start": s, "goal": g})
    return scenarios

def build_multi_location_scenarios(graph, seed=42):
    rng = random.Random(seed); scenarios = []
    for n in MULTI_LOCATION_SIZES:
        pair = select_multi_location_nodes(graph, n, rng)
        if pair is None: print(f"[WARN] Could not build M{n}"); continue
        s, goals = pair
        scenarios.append({"name": f"M{n}", "start": s, "goals": goals})
    return scenarios

def safe_stat(values, fn):
    clean = [v for v in values if v is not None and not math.isnan(v) and not math.isinf(v)]
    if not clean: return None
    try: return fn(clean)
    except: return None

def aggregate_search_summary(raw):
    from collections import defaultdict
    groups = defaultdict(list)
    for r in raw:
        if r.group=="search": groups[(r.algorithm, r.scenario)].append(r)
    rows = []
    for (algo, scenario), records in sorted(groups.items()):
        suc=[r for r in records if r.success]
        t=[r.time_ms for r in suc]; c=[r.total_cost for r in suc]
        d=[r.distance_km for r in suc]; e=[r.expanded_nodes for r in suc]
        m=[r.peak_memory_kb for r in suc if r.peak_memory_kb>0]
        rows.append({
            "Algorithm": algo, "Scenario": scenario,
            "Total_Runs": len(records), "Successful_Runs": len(suc),
            "Success_Rate_%": round(100.0*len(suc)/max(1,len(records)),1),
            "Avg_Time_ms": round(safe_stat(t,statistics.mean) or 0,3),
            "Median_Time_ms": round(safe_stat(t,statistics.median) or 0,3),
            "Min_Time_ms": round(safe_stat(t,min) or 0,3),
            "Max_Time_ms": round(safe_stat(t,max) or 0,3),
            "Std_Time_ms": round(safe_stat(t,statistics.stdev) or 0,3) if len(t)>1 else 0,
            "Best_Cost": round(safe_stat(c,min) or 0,6),
            "Avg_Cost": round(safe_stat(c,statistics.mean) or 0,6),
            "Median_Cost": round(safe_stat(c,statistics.median) or 0,6),
            "Worst_Cost": round(safe_stat(c,max) or 0,6),
            "Std_Cost": round(safe_stat(c,statistics.stdev) or 0,6) if len(c)>1 else 0,
            "Avg_Distance_km": round(safe_stat(d,statistics.mean) or 0,4),
            "Avg_Expanded_Nodes": round(safe_stat(e,statistics.mean) or 0,1),
            "Avg_Peak_Memory_KB": round(safe_stat(m,statistics.mean) or 0,2),
            "Max_Peak_Memory_KB": round(safe_stat(m,max) or 0,2),
        })
    return rows

def aggregate_optimization_summary(raw):
    from collections import defaultdict
    groups = defaultdict(list)
    for r in raw:
        if r.group=="optimization": groups[(r.algorithm, r.scenario)].append(r)
    rows = []
    for (algo, scenario), records in sorted(groups.items()):
        try: n_loc=int(scenario.lstrip("M"))
        except: n_loc=-1
        suc=[r for r in records if r.success]
        c=[r.total_cost for r in suc]; d=[r.distance_km for r in suc]
        t=[r.time_ms for r in suc]; m=[r.peak_memory_kb for r in suc if r.peak_memory_kb>0]
        rows.append({
            "Algorithm": algo, "Scenario": scenario, "Locations": n_loc,
            "Total_Runs": len(records), "Successful_Runs": len(suc),
            "Success_Rate_%": round(100.0*len(suc)/max(1,len(records)),1),
            "Best_Cost": round(safe_stat(c,min) or 0,6),
            "Avg_Cost": round(safe_stat(c,statistics.mean) or 0,6),
            "Median_Cost": round(safe_stat(c,statistics.median) or 0,6),
            "Worst_Cost": round(safe_stat(c,max) or 0,6),
            "Std_Cost": round(safe_stat(c,statistics.stdev) or 0,6) if len(c)>1 else 0,
            "Avg_Distance_km": round(safe_stat(d,statistics.mean) or 0,4),
            "Avg_Time_ms": round(safe_stat(t,statistics.mean) or 0,3),
            "Median_Time_ms": round(safe_stat(t,statistics.median) or 0,3),
            "Std_Time_ms": round(safe_stat(t,statistics.stdev) or 0,3) if len(t)>1 else 0,
            "Avg_Peak_Memory_KB": round(safe_stat(m,statistics.mean) or 0,2),
            "Max_Peak_Memory_KB": round(safe_stat(m,max) or 0,2),
        })
    return rows

RAW_CSV_FIELDS = ["algorithm","group","scenario","run","seed","success","time_ms",
                  "path_length","total_cost","distance_km","visited_nodes",
                  "expanded_nodes","peak_memory_kb","error_type","error_msg"]

def save_raw_csv(records, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=RAW_CSV_FIELDS); w.writeheader()
        for r in records:
            w.writerow({"algorithm":r.algorithm,"group":r.group,"scenario":r.scenario,
                        "run":r.run,"seed":"" if r.seed is None else r.seed,
                        "success":r.success,"time_ms":r.time_ms,"path_length":r.path_length,
                        "total_cost":r.total_cost,"distance_km":r.distance_km,
                        "visited_nodes":r.visited_nodes,"expanded_nodes":r.expanded_nodes,
                        "peak_memory_kb":r.peak_memory_kb,"error_type":r.error_type,
                        "error_msg":r.error_msg})

def save_dict_csv(rows, path):
    if not rows: return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

def _col(v, w, a=">"):
    s = str(v) if v is not None else "N/A"
    return f"{s:{a}{w}}"

def _print_table(rows, hdrs, km):
    sep="+".join("-"*(w+2) for _,w,_ in hdrs); sep=f"+{sep}+"
    hl="|".join(f" {h:{a}{w}} " for h,w,a in hdrs); hl=f"|{hl}|"
    print(sep); print(hl); print(sep)
    for row in rows:
        l="|".join(f" {_col(row.get(km[h],'N/A'),w,a)} " for h,w,a in hdrs)
        print(f"|{l}|")
    print(sep)

def print_search_summary(rows):
    if not rows: print("  (no data)"); return
    hdrs=[("Algorithm",14,"<"),("Scenario",10,"<"),("Succ%",6,">"),
          ("AvgTime(ms)",12,">"),("MedTime(ms)",12,">"),("StdTime",8,">"),
          ("AvgCost",10,">"),("AvgDist(km)",12,">"),("ExpandedN",10,">"),("MemKB",8,">")]
    km={"Algorithm":"Algorithm","Scenario":"Scenario","Succ%":"Success_Rate_%",
        "AvgTime(ms)":"Avg_Time_ms","MedTime(ms)":"Median_Time_ms","StdTime":"Std_Time_ms",
        "AvgCost":"Avg_Cost","AvgDist(km)":"Avg_Distance_km",
        "ExpandedN":"Avg_Expanded_Nodes","MemKB":"Avg_Peak_Memory_KB"}
    _print_table(rows, hdrs, km)

def print_optimization_summary(rows):
    if not rows: print("  (no data)"); return
    hdrs=[("Algorithm",20,"<"),("Scenario",8,"<"),("Locs",4,">"),("Succ%",6,">"),
          ("BestCost",10,">"),("AvgCost",10,">"),("MedCost",10,">"),("StdCost",8,">"),
          ("AvgTime(ms)",12,">"),("MemKB",8,">")]
    km={"Algorithm":"Algorithm","Scenario":"Scenario","Locs":"Locations",
        "Succ%":"Success_Rate_%","BestCost":"Best_Cost","AvgCost":"Avg_Cost",
        "MedCost":"Median_Cost","StdCost":"Std_Cost","AvgTime(ms)":"Avg_Time_ms",
        "MemKB":"Avg_Peak_Memory_KB"}
    _print_table(rows, hdrs, km)

def save_findings(findings, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path,"w",encoding="utf-8") as f:
        f.write("# BENCHMARK_FINDINGS.md\n\n")
        f.write("Findings during the benchmark run.\n**Do NOT modify algorithm implementations** without team review.\n\n")
        if not findings: f.write("No findings recorded.\n"); return
        for i,fnd in enumerate(findings,1):
            f.write(f"## Finding {i}\n\n| Field | Value |\n|-------|-------|\n")
            f.write(f"| Algorithm | `{fnd.algorithm}` |\n")
            f.write(f"| File | `{fnd.file}` |\n")
            f.write(f"| Function | `{fnd.function}` |\n")
            f.write(f"| Scenario | `{fnd.scenario}` |\n")
            f.write(f"| Observed | {fnd.observed} |\n")
            f.write(f"| Expected | {fnd.expected} |\n")
            f.write(f"| Possible Cause | {fnd.possible_cause} |\n\n")

def benchmark_search_algorithms(graph, scenarios, algo_filter, n_det, n_stoch, findings):
    raw = []
    for algo_name, adapter_fn, group, is_stochastic, is_avail in SEARCH_ALGORITHMS:
        if not is_avail: print(f"[SKIP] {algo_name}"); continue
        if algo_filter and algo_filter.lower() not in algo_name.lower(): continue
        n_runs = n_stoch if is_stochastic else n_det
        seeds = STOCHASTIC_SEEDS[:n_runs] if is_stochastic else [None]*n_runs
        for scenario in scenarios:
            start=scenario["start"]; goal=scenario["goal"]; sname=scenario["name"]
            print(f"  [Warmup] {algo_name} - {sname}")
            warmup(adapter_fn, graph, start, goal)
            for run_i,seed in enumerate(seeds,1):
                print(f"  [Benchmark] {algo_name} - {sname} - Run {run_i}/{n_runs}")
                rec = run_single_benchmark(algo_name, adapter_fn, graph, start, goal,
                                           run_i, seed, sname, group, False)
                raw.append(rec)
                if not rec.success and rec.error_type:
                    findings.append(FindingRecord(
                        algorithm=algo_name,
                        file=f"src/algorithms/{algo_name.lower()}.py",
                        function=algo_name.lower(), scenario=sname,
                        observed=f"{rec.error_type}: {rec.error_msg}",
                        expected="SearchResult success=True",
                        possible_cause="See error."))
    return raw

def benchmark_optimization_algorithms(graph, scenarios, algo_filter, n_runs, findings):
    raw=[]; seeds=STOCHASTIC_SEEDS[:n_runs]
    for algo_name, adapter_fn, group, is_stochastic, is_avail in OPTIMIZATION_ALGORITHMS:
        if not is_avail: print(f"[SKIP] {algo_name}"); continue
        if algo_filter and algo_filter.lower() not in algo_name.lower(): continue
        for scenario in scenarios:
            start=scenario["start"]; goals=scenario["goals"]; sname=scenario["name"]
            print(f"  [Warmup] {algo_name} - {sname}")
            warmup(adapter_fn, graph, start, goals, True)
            for run_i,seed in enumerate(seeds,1):
                print(f"  [Benchmark] {algo_name} - {sname} - Run {run_i}/{n_runs}")
                rec = run_single_benchmark(algo_name, adapter_fn, graph, start, goals,
                                           run_i, seed, sname, group, True)
                raw.append(rec)
                if not rec.success and rec.error_type:
                    findings.append(FindingRecord(
                        algorithm=algo_name,
                        file="src/algorithms/simulated_annealing.py",
                        function="simulated_annealing", scenario=sname,
                        observed=f"{rec.error_type}: {rec.error_msg}",
                        expected="SearchResult success=True",
                        possible_cause="See error."))
    return raw

def parse_args():
    p = argparse.ArgumentParser(description="Route optimization algorithm benchmark.")
    p.add_argument("--runs", type=int, default=None)
    p.add_argument("--stochastic-runs", type=int, default=None)
    p.add_argument("--algorithm", type=str, default=None)
    p.add_argument("--group", choices=["search","optimization","all"], default="all")
    p.add_argument("--dataset", type=str, default=DEFAULT_DATASET)
    p.add_argument("--output", type=str, default="results")
    return p.parse_args()

def main():
    args = parse_args()
    n_det   = args.runs            if args.runs            else DETERMINISTIC_RUNS
    n_stoch = args.stochastic_runs if args.stochastic_runs else STOCHASTIC_RUNS
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    dataset = args.dataset; available = get_json_datasets()
    if dataset not in available:
        print(f"[WARN] Dataset not found: {dataset}")
        if available: dataset = available[0]; print(f"[INFO] Using: {dataset}")
        else: print("[ERROR] No datasets."); sys.exit(1)
    print(f"\n{'='*60}\n  HCMUS AI Route Optimization - Algorithm Benchmark\n{'='*60}")
    print(f"  Dataset: {dataset}  |  Det: {n_det}  |  Stoch: {n_stoch}  |  Group: {args.group}")
    print(f"  Output: {out.resolve()}\n{'='*60}\n")
    print("[1/6] Loading graph...")
    graph = load_graph(dataset)
    nc=len(graph.nodes); ec=sum(len(v) for v in graph.adjacency_list.values())
    print(f"      Nodes: {nc}  |  Directed edges: {ec}\n")
    if nc<4: print("[ERROR] Graph too small."); sys.exit(1)
    print("[2/6] Building scenarios...")
    ss=build_point_to_point_scenarios(graph); ms=build_multi_location_scenarios(graph)
    for sc in ss: print(f"  {sc['name']:12s}: {sc['start']} -> {sc['goal']} ({sc['description']})")
    for sc in ms: print(f"  {sc['name']:6s}: start={sc['start']} goals={sc['goals']}")
    print()
    all_raw=[]; findings=[]
    findings.append(FindingRecord(
        algorithm="BeamSearch", file="src/algorithms/beam_search.py",
        function="beam_search", scenario="ALL",
        observed="edge.calculate_cost(mode=mode) at lines 75,110. Edge.calculate_cost() has no 'mode' param.",
        expected="edge.calculate_cost() without mode kwarg",
        possible_cause="beam_search.py was written assuming Edge supports a mode str. Fix: remove mode=mode from both call sites."))
    if args.group in ("search","all"):
        print("[3/6] Group A: Point-to-Point...")
        all_raw.extend(benchmark_search_algorithms(graph,ss,args.algorithm,n_det,n_stoch,findings))
        print()
    if args.group in ("optimization","all"):
        print("[4/6] Group B: Multi-Location...")
        all_raw.extend(benchmark_optimization_algorithms(graph,ms,args.algorithm,n_stoch,findings))
        print()
    print("[5/6] Aggregating...")
    ss2=aggregate_search_summary(all_raw); ms2=aggregate_optimization_summary(all_raw)
    rp=out/"benchmark_raw.csv"; sp=out/"benchmark_search_summary.csv"
    op=out/"benchmark_optimization_summary.csv"; fp=out/"BENCHMARK_FINDINGS.md"
    save_raw_csv(all_raw,rp); save_dict_csv(ss2,sp); save_dict_csv(ms2,op); save_findings(findings,fp)
    print("[6/6] Results\n")
    if ss2: print("-- Group A: Point-to-Point Search --"); print_search_summary(ss2); print()
    if ms2: print("-- Group B: Multi-Location Optimization --"); print_optimization_summary(ms2); print()
    print(f"{'='*60}\nBenchmark completed.\n  Raw:     {rp.resolve()}\n  Search:  {sp.resolve()}\n  Optim:   {op.resolve()}\n  Findings:{fp.resolve()}\n{'='*60}")

if __name__ == "__main__":
    main()