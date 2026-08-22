
from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import time
import tracemalloc
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "benchmarks" / "results"
DEFAULT_DATASETS = (
    "map_district_3.json",
)

from src.models.graph_factory import build_graph

# Dynamic import to handle incomplete algorithm implementations gracefully
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
_bidir_fn = _try_import("bidirectional_search","src.algorithms.bidirectional_search")
_ga_fn    = _try_import("genetic_algorithm",  "src.algorithms.genetic_algorithm")
_sa_fn    = _try_import("simulated_annealing","src.algorithms.simulated_annealing")
_nn2opt_fn = _try_import("nearest_neighbor_2opt", "src.algorithms.nearest_neighbor_2opt")

# Configuration constants for heuristic / meta-heuristic algorithms
BEAM_WIDTH = 10
GA_POPULATION_SIZE = 50
GA_GENERATIONS = 100
GA_MUTATION_RATE = 0.2
SA_INITIAL_TEMP = 1000.0
SA_DECAY_RATE = 0.995

# Registry format: key -> (display_name, function, group, is_stochastic)
# group="search"        -> runs single point-to-point scenarios only
# group="optimization"  -> runs multi-location scenarios only
# group="both"          -> runs both scenario types
ALGORITHM_REGISTRY = {
    "dfs": ("DFS", _dfs_fn, "search", False),
    "bfs": ("BFS", _bfs_fn, "search", False),
    "ucs": ("UCS", _ucs_fn, "search", False),
    "a_star": ("A*", _astar_fn, "search", False),
    "beam": ("BeamSearch", _beam_fn, "search", False),
    "bidirectional": ("Bidirectional", _bidir_fn, "search", False),
    "ga": ("GeneticAlgo", _ga_fn, "both", True),
    "sa": ("SimulatedAnnealing", _sa_fn, "optimization", True),
    "nn2opt": ("NN+2Opt", _nn2opt_fn, "optimization", False),
}

@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    scenario_type: str # e.g. "S1_Short", "M5"
    start_id: str
    goal_id: str
    intermediate_ids: tuple[str, ...]
    is_multi: bool

@dataclass
class FindingRecord:
    algorithm: str
    scenario: str
    observed: str
    expected: str
    possible_cause: str

RAW_FIELDS = (
    "timestamp_utc", "dataset", "graph_nodes", "graph_edges",
    "scenario_id", "scenario_type", "start_id", "goal_id", "intermediate_ids",
    "algorithm_key", "algorithm", "repeat", "success", "path_valid",
    "runtime_ms", "peak_memory_kb", "path_nodes", "visited_nodes", "search_steps",
    "reported_cost", "weighted_path_cost", "distance_km", "error"
)

SUMMARY_FIELDS = (
    "dataset", "graph_nodes", "graph_edges", "algorithm_key", "algorithm",
    "runs", "successful_runs", "success_rate_pct",
    "runtime_mean_ms", "runtime_median_ms", "runtime_stdev_ms", "runtime_min_ms", "runtime_max_ms",
    "peak_memory_mean_kb", "visited_nodes_mean", "path_nodes_mean",
    "weighted_path_cost_mean", "distance_km_mean"
)

def _graph_edge_count(graph) -> int:
    return sum(len(edges) for edges in graph.adjacency_list.values())

def _bfs_hop_distance(graph, start_id: str) -> dict[str, int]:
    dist = {start_id: 0}
    q = deque([start_id])
    while q:
        node = q.popleft()
        for edge in graph.get_neighbors(node):
            nbr = edge.to_node
            if nbr not in dist:
                dist[nbr] = dist[node] + 1
                q.append(nbr)
    return dist

def select_scenario_nodes(graph, hop_pct_range, rng) -> tuple[str, str] | None:
    node_ids = list(graph.nodes.keys())
    if len(node_ids) < 2: return None
    lo_pct, hi_pct = hop_pct_range
    candidates = []
    for start in rng.sample(node_ids, min(20, len(node_ids))):
        hd = _bfs_hop_distance(graph, start)
        if len(hd) < 2: continue
        mx = max(hd.values())
        if mx == 0: continue
        lo = max(1, int(lo_pct * mx))
        hi = max(lo, int(hi_pct * mx))
        eligible = [n for n, d in hd.items() if lo <= d <= hi]
        if eligible:
            g = rng.choice(eligible)
            candidates.append((start, g, hd[g]))
    if not candidates: return None
    candidates.sort(key=lambda x: x[2])
    s, g, _ = candidates[len(candidates)//2]
    return s, g

def select_multi_location_nodes(graph, n_goals, rng) -> tuple[str, list[str]] | None:
    node_ids = list(graph.nodes.keys())
    if len(node_ids) < n_goals + 1: return None
    for _ in range(30):
        start = rng.choice(node_ids)
        hd = _bfs_hop_distance(graph, start)
        reachable = [n for n in hd if n != start]
        if len(reachable) >= n_goals:
            return start, rng.sample(reachable, n_goals)
    return None

def build_scenarios(graph, count: int, seed: int, include_multi: bool = True) -> list[Scenario]:
    """Build scenarios based on length properties and multi-location counts."""
    scenarios = []
    rng = random.Random(seed)
    
    # Point-to-Point Scenarios
    scenario_defs = [
        {"type": "S1_Short",  "hop_pct": (0.0,  0.15)},
        {"type": "S2_Medium", "hop_pct": (0.25, 0.45)},
        {"type": "S3_Long",   "hop_pct": (0.55, 0.80)},
    ]
    
    for idx, sdef in enumerate(scenario_defs):
        for rep in range(count):
            pair = select_scenario_nodes(graph, sdef["hop_pct"], rng)
            if pair:
                scenarios.append(Scenario(
                    scenario_id=f"{sdef['type']}_{rep+1}",
                    scenario_type=sdef["type"],
                    start_id=pair[0], goal_id=pair[1],
                    intermediate_ids=(),
                    is_multi=False
                ))

    # Multi-location Scenarios
    if include_multi:
        multi_sizes = [3, 5, 8]
        for msize in multi_sizes:
            for rep in range(count):
                pair = select_multi_location_nodes(graph, msize, rng)
                if pair:
                    s, goals = pair
                    scenarios.append(Scenario(
                        scenario_id=f"M{msize}_{rep+1}",
                        scenario_type=f"M{msize}",
                        start_id=s, goal_id=goals[-1], # The last goal is passed as end_id for some algos
                        intermediate_ids=tuple(goals[:-1]),
                        is_multi=True
                    ))
    return scenarios

def _run_algorithm(algorithm_key: str, graph, scenario: Scenario, seed: int = None):
    _, fn, group, is_stoch = ALGORITHM_REGISTRY[algorithm_key]
    if fn is None:
        raise NotImplementedError(f"Algorithm {algorithm_key} not available.")
    
    if is_stoch and seed is not None:
        random.seed(seed)

    if not scenario.is_multi:
        # --- Single point-to-point ---
        kwargs = {}
        if algorithm_key == "beam":
            kwargs["beam_width"] = BEAM_WIDTH
        elif algorithm_key == "ga":
            # GA treats a single goal as a one-element goal list
            return fn(graph, scenario.start_id, [scenario.goal_id],
                      population_size=GA_POPULATION_SIZE,
                      generations=GA_GENERATIONS,
                      mutation_rate=GA_MUTATION_RATE)
        return fn(graph, scenario.start_id, scenario.goal_id, **kwargs)
    else:
        # --- Multi-location ---
        goals = list(scenario.intermediate_ids) + [scenario.goal_id]
        if algorithm_key == "ga":
            return fn(graph, scenario.start_id, goals,
                      population_size=GA_POPULATION_SIZE,
                      generations=GA_GENERATIONS,
                      mutation_rate=GA_MUTATION_RATE)
        elif algorithm_key == "sa":
            return fn(graph, scenario.start_id, goals,
                      respect_goal_order=False,
                      initial_temp=SA_INITIAL_TEMP,
                      decay_rate=SA_DECAY_RATE)
        elif algorithm_key == "nn2opt":
            return fn(graph, scenario.start_id, goals)
        else:
            raise ValueError(f"Algorithm {algorithm_key} cannot run multi-location scenarios")

def _validate_path(graph, path: list[str], scenario: Scenario):
    if not path:
        return False, "Path is empty", math.inf, math.inf
    if path[0] != scenario.start_id:
        return False, f"Starts at {path[0]} instead of {scenario.start_id}", math.inf, math.inf
    
    if scenario.is_multi:
        ps = set(path)
        required = set(scenario.intermediate_ids) | {scenario.goal_id}
        missing = required - ps
        if missing:
            return False, f"Missing goals: {missing}", math.inf, math.inf
    else:
        if path[-1] != scenario.goal_id:
            return False, f"Ends at {path[-1]} instead of {scenario.goal_id}", math.inf, math.inf

    weighted_cost = 0.0
    distance_km = 0.0
    for source, target in zip(path, path[1:]):
        edge = graph.get_edge(source, target)
        if edge is None:
            return False, f"Invalid edge {source}->{target}", math.inf, math.inf
        weighted_cost += float(edge.calculate_cost())
        distance_km += float(edge.distance)
    return True, "", weighted_cost, distance_km

def benchmark_once(
    algorithm_key: str, graph, dataset: str, scenario: Scenario, repeat: int, seed: int
) -> tuple[dict, FindingRecord | None]: # Runtime chính xác, Memory đúng, không bị nhiễu
    gc.collect() 
    error_msg = ""
    result = None
    finding = None
    tracemalloc.start()
    started_at = time.perf_counter_ns()
    try:
        result = _run_algorithm(algorithm_key, graph, scenario, seed=seed)
    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {str(exc)[:300]}"
        finding = FindingRecord(algorithm_key, scenario.scenario_id, error_msg, "Success", "Exception thrown")
    
    runtime_ms = (time.perf_counter_ns() - started_at) / 1_000_000
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    path = list(getattr(result, "path", []) or [])
    path_valid, val_reason, weighted_cost, distance_km = _validate_path(graph, path, scenario)
    success = bool(getattr(result, "success", False)) and path_valid and not error_msg
    
    if not success and not finding and val_reason:
         finding = FindingRecord(algorithm_key, scenario.scenario_id, val_reason, "Valid Path", "Path validation failed")

    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset,
        "graph_nodes": len(graph.nodes),
        "graph_edges": _graph_edge_count(graph),
        "scenario_id": scenario.scenario_id,
        "scenario_type": scenario.scenario_type,
        "start_id": scenario.start_id,
        "goal_id": scenario.goal_id,
        "intermediate_ids": ";".join(scenario.intermediate_ids),
        "algorithm_key": algorithm_key,
        "algorithm": ALGORITHM_REGISTRY[algorithm_key][0],
        "repeat": repeat,
        "success": success,
        "path_valid": path_valid,
        "runtime_ms": round(runtime_ms, 6),
        "peak_memory_kb": round(peak_bytes / 1024, 6),
        "path_nodes": len(path),
        "visited_nodes": len(getattr(result, "visited_order", []) or []),
        "search_steps": len(getattr(result, "steps", []) or []),
        "reported_cost": round(float(getattr(result, "total_cost", 0.0)), 9) if result is not None and getattr(result, "total_cost", None) is not None else "",
        "weighted_path_cost": round(weighted_cost, 9) if math.isfinite(weighted_cost) else "",
        "distance_km": round(distance_km, 9) if math.isfinite(distance_km) else "",
        "error": error_msg,
    }
    return row, finding

def _mean(rows: list[dict], key: str):
    values = [float(row[key]) for row in rows if row.get(key) not in ("", None)]
    return statistics.fmean(values) if values else 0.0

def summarize_rows(raw_rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in raw_rows:
        grouped[(row["dataset"], row["algorithm_key"])].append(row)

    summaries = []
    for (dataset, algorithm_key), rows in grouped.items():
        successful = [row for row in rows if row["success"]]
        runtimes = [float(row["runtime_ms"]) for row in rows]
        summaries.append({
            "dataset": dataset,
            "graph_nodes": int(rows[0]["graph_nodes"]),
            "graph_edges": int(rows[0]["graph_edges"]),
            "algorithm_key": algorithm_key,
            "algorithm": rows[0]["algorithm"],
            "runs": len(rows),
            "successful_runs": len(successful),
            "success_rate_pct": round(100 * len(successful) / len(rows), 3),
            "runtime_mean_ms": round(statistics.fmean(runtimes), 6),
            "runtime_median_ms": round(statistics.median(runtimes), 6),
            "runtime_stdev_ms": round(statistics.stdev(runtimes), 6) if len(runtimes) > 1 else 0.0,
            "runtime_min_ms": round(min(runtimes), 6),
            "runtime_max_ms": round(max(runtimes), 6),
            "peak_memory_mean_kb": round(_mean(rows, "peak_memory_kb"), 6),
            "visited_nodes_mean": round(_mean(successful, "visited_nodes"), 3),
            "path_nodes_mean": round(_mean(successful, "path_nodes"), 3),
            "weighted_path_cost_mean": round(_mean(successful, "weighted_path_cost"), 9),
            "distance_km_mean": round(_mean(successful, "distance_km"), 9),
        })
    summaries.sort(key=lambda row: (int(row["graph_nodes"]), row["algorithm_key"]))
    return summaries

def _write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

def _git_value(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=PROJECT_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"

def write_metadata(path: Path, args, scenarios_by_dataset: dict[str, list[Scenario]]):
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
        "logical_cpu_count": os.cpu_count(),
        "git_branch": _git_value("branch", "--show-current"),
        "git_commit": _git_value("rev-parse", "HEAD"),
        "configuration": {
            "datasets": args.datasets,
            "algorithms": args.algorithms,
            "scenarios_per_type": args.scenarios,
            "repeats": args.repeats,
            "warmups": args.warmups,
            "seed": args.seed,
        },
        "scenario_definitions": {
            dataset: [asdict(scenario) for scenario in scenarios]
            for dataset, scenarios in scenarios_by_dataset.items()
        },
        "measurement_notes": {
            "runtime": "perf_counter_ns; excludes JSON loading and warm-up runs",
            "memory": "tracemalloc peak Python allocation; excludes native allocations",
            "cost": "recomputed from Edge.calculate_cost for cross-algorithm comparison",
        },
    }
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

def save_findings(findings: list[FindingRecord], path: Path):
    with path.open("w", encoding="utf-8") as f:
        f.write("# BENCHMARK_FINDINGS.md\n\n")
        f.write("Findings and errors discovered during the benchmark run.\n\n")
        if not findings:
            f.write("No findings recorded. All runs completed successfully.\n")
            return
        for i, fnd in enumerate(findings, 1):
            f.write(f"## Finding {i}\n\n| Field | Value |\n|-------|-------|\n")
            f.write(f"| Algorithm | `{fnd.algorithm}` |\n")
            f.write(f"| Scenario | `{fnd.scenario}` |\n")
            f.write(f"| Observed | {fnd.observed} |\n")
            f.write(f"| Expected | {fnd.expected} |\n")
            f.write(f"| Possible Cause | {fnd.possible_cause} |\n\n")

def create_charts(summary_rows: list[dict], output_dir: Path) -> list[Path]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        print("[WARN] Chart generation requires matplotlib. Run: pip install -r requirements.txt")
        return []

    datasets = sorted(
        {row["dataset"] for row in summary_rows},
        key=lambda dataset: next(int(row["graph_nodes"]) for row in summary_rows if row["dataset"] == dataset),
    )
    algorithms = [key for key in ALGORITHM_REGISTRY.keys() if any(row["algorithm_key"] == key for row in summary_rows)]
    lookup = {(row["dataset"], row["algorithm_key"]): row for row in summary_rows}
    x_positions = list(range(len(datasets)))
    width = 0.8 / max(1, len(algorithms))

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    metrics = (
        ("runtime_mean_ms", "Runtime trung bình (ms)", True),
        ("peak_memory_mean_kb", "Peak Python memory (KB)", True),
        ("visited_nodes_mean", "Số node được thuật toán ghi nhận", True),
        ("success_rate_pct", "Tỷ lệ thành công (%)", False),
    )
    for axis, (metric, title, use_log) in zip(axes.flat, metrics):
        for algorithm_index, algorithm_key in enumerate(algorithms):
            values = [float(lookup.get((dataset, algorithm_key), {}).get(metric, 0.0)) for dataset in datasets]
            offsets = [position - 0.4 + width / 2 + algorithm_index * width for position in x_positions]
            axis.bar(offsets, values, width=width, label=ALGORITHM_REGISTRY[algorithm_key][0])
        axis.set_title(title)
        axis.set_xticks(x_positions)
        axis.set_xticklabels(
            [Path(dataset).stem.replace("map_", "").replace("_district", "") for dataset in datasets],
            rotation=15, ha="right",
        )
        axis.grid(axis="y", alpha=0.25)
        if use_log and any(float(row.get(metric, 0.0)) > 0 for row in summary_rows):
            axis.set_yscale("log")
            
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.suptitle("Tổng quan hiệu năng thuật toán tìm đường (Unified Benchmark)", y=0.995, fontsize=15)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.965), ncol=max(1, len(labels)))
    fig.tight_layout(rect=(0, 0, 1, 0.90), h_pad=3.5, w_pad=4.0)
    overview_path = output_dir / "performance_overview.png"
    fig.savefig(overview_path, dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(10, 6))
    for algorithm_key in algorithms:
        rows = [row for row in summary_rows if row["algorithm_key"] == algorithm_key]
        rows.sort(key=lambda row: int(row["graph_nodes"]))
        if not rows: continue
        axis.plot(
            [int(row["graph_nodes"]) for row in rows],
            [float(row["runtime_mean_ms"]) for row in rows],
            marker="o", linewidth=2, label=ALGORITHM_REGISTRY[algorithm_key][0],
        )
    axis.set_xlabel("Số node của graph")
    axis.set_ylabel("Runtime trung bình (ms, log scale)")
    axis.set_yscale("log")
    axis.set_title("Khả năng mở rộng theo kích thước graph")
    axis.grid(alpha=0.3)
    axis.legend()
    fig.tight_layout()
    scaling_path = output_dir / "runtime_scaling.png"
    fig.savefig(scaling_path, dpi=160)
    plt.close(fig)
    return [overview_path, scaling_path]

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Unified Benchmark for Route Algorithms.")
    parser.add_argument("--datasets", nargs="+", default=list(DEFAULT_DATASETS))
    
    available_algos = [k for k, v in ALGORITHM_REGISTRY.items() if v[1] is not None]
    parser.add_argument("--algorithms", nargs="+", choices=available_algos, default=available_algos)
    
    parser.add_argument("--scenarios", type=int, default=1, help="Number of scenarios per type (S1, S2, M3...)")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260808)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-charts", action="store_true")
    args = parser.parse_args(argv)
    if args.scenarios < 1 or args.repeats < 1 or args.warmups < 0:
        parser.error("scenarios/repeats must be >= 1 and warmups must be >= 0")
    return args

def main(argv=None) -> int:
    args = parse_args(argv)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_rows = []
    findings = []
    scenarios_by_dataset = {}

    print(f"{'='*60}\n  HCMUS AI Route Optimization - Unified Benchmark\n{'='*60}")
    print(f"  Algorithms: {args.algorithms}")
    
    for dataset_index, dataset in enumerate(args.datasets):
        dataset_path = DATA_DIR / dataset
        if not dataset_path.exists():
            print(f"[ERROR] Dataset not found: {dataset_path}", file=sys.stderr)
            return 2
        print(f"[LOAD] {dataset}")
        graph = build_graph(str(dataset_path))
        scenarios = build_scenarios(graph, count=args.scenarios, seed=args.seed + dataset_index)
        
        if not scenarios:
            print(f"[ERROR] Could not build scenarios in {dataset}.", file=sys.stderr)
            continue
            
        scenarios_by_dataset[dataset] = scenarios

        for scenario in scenarios:
            for algorithm_key in args.algorithms:
                algo_name, fn, group, is_stoch = ALGORITHM_REGISTRY[algorithm_key]
                if fn is None: continue
                if scenario.is_multi and group == "search": continue # Point-to-point algos skip multi scenarios
                if not scenario.is_multi and group == "optimization": continue # Optimization algos skip point-to-point scenarios

                # Warmup
                for _ in range(args.warmups):
                    try: _run_algorithm(algorithm_key, graph, scenario, seed=0)
                    except: pass
                
                # Benchmark Repeats
                for repeat in range(1, args.repeats + 1):
                    row, finding = benchmark_once(
                        algorithm_key, graph, dataset, scenario, repeat, seed=args.seed + repeat if is_stoch else None
                    )
                    raw_rows.append(row)
                    if finding: findings.append(finding)
                    
                    status = "OK" if row["success"] else "FAIL"
                    print(
                        f"  [{status}] {dataset} {scenario.scenario_id} "
                        f"{row['algorithm']}: {row['runtime_ms']:.3f} ms, "
                        f"{row['peak_memory_kb']:.1f} KB"
                    )

    if not raw_rows:
        print("[ERROR] No valid benchmark runs completed.", file=sys.stderr)
        return 1

    summary_rows = summarize_rows(raw_rows)
    raw_path = output_dir / "benchmark_raw.csv"
    summary_path = output_dir / "benchmark_summary.csv"
    metadata_path = output_dir / "benchmark_metadata.json"
    findings_path = output_dir / "BENCHMARK_FINDINGS.md"
    
    _write_csv(raw_path, raw_rows, RAW_FIELDS)
    _write_csv(summary_path, summary_rows, SUMMARY_FIELDS)
    write_metadata(metadata_path, args, scenarios_by_dataset)
    save_findings(findings, findings_path)
    
    artifacts = [raw_path, summary_path, metadata_path, findings_path]
    if not args.no_charts:
        artifacts.extend(create_charts(summary_rows, output_dir))

    print("\n[DONE] Generated artifacts:")
    for artifact in artifacts:
        try: display_path = artifact.relative_to(PROJECT_ROOT)
        except ValueError: display_path = artifact.name
        print(f"  - {display_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
