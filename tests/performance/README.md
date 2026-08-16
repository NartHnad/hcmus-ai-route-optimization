# Algorithm Benchmark — tests/performance/

This directory contains the performance benchmark suite for all 7 route-optimization algorithms.

## Quick Start

```bash
# From project root
python tests/performance/benchmark_algorithms.py

# With options
python tests/performance/benchmark_algorithms.py --runs 5
python tests/performance/benchmark_algorithms.py --group search
python tests/performance/benchmark_algorithms.py --group optimization
python tests/performance/benchmark_algorithms.py --algorithm astar
python tests/performance/benchmark_algorithms.py --dataset map_district_1.json
python tests/performance/benchmark_algorithms.py --output my_results/
```

## Output Files

| File | Description |
|------|-------------|
| `results/benchmark_raw.csv` | Every individual run — one row per run |
| `results/benchmark_search_summary.csv` | Aggregated statistics for Group A |
| `results/benchmark_optimization_summary.csv` | Aggregated statistics for Group B |
| `results/BENCHMARK_FINDINGS.md` | Bugs and anomalies detected during benchmark |

## Algorithm Classification

### Group A — Point-to-Point Search (`route_mode = "single"`)

| Algorithm | Key | Stochastic | Runs |
|-----------|-----|-----------|------|
| BFS | `bfs` | No | 10 |
| DFS | `dfs` | No | 10 |
| UCS | `ucs` | No | 10 |
| A\* | `astar` | No | 10 |
| Beam Search | `beam` | No | 10 |
| Genetic Algorithm | `ga` | Yes | 30 |

**Important**: GA solves `(graph, start, goal)` — the same interface as BFS/DFS. It belongs to Group A.

### Group B — Multi-Location TSP (`route_mode = "multi"`)

| Algorithm | Key | Stochastic | Runs |
|-----------|-----|-----------|------|
| Simulated Annealing | `sa` | Yes | 30 |

**Important**: SA solves `(graph, start, [goal1, goal2, ...])` — a different problem. Do NOT compare SA cost directly against Group A costs.

## Scenarios

### Point-to-Point Scenarios

| Scenario | Hop Distance | Description |
|----------|-------------|-------------|
| S1_Short | 0–15% of max | Start and goal are nearby |
| S2_Medium | 25–45% of max | Medium separation |
| S3_Long | 55–80% of max | Far-apart start and goal |

Node pairs are selected automatically from the loaded graph using BFS hop distance.

### Multi-Location Scenarios

| Scenario | Intermediate Goals |
|----------|-----------------|
| M3 | 3 goals |
| M5 | 5 goals |
| M8 | 8 goals |

All scenarios use the same start node and goal set for fair comparison.

## Metric Definitions

| Metric | Definition |
|--------|------------|
| `time_ms` | Wall-clock execution time in milliseconds (`perf_counter`) |
| `total_cost` | Canonical edge cost: `alpha*norm_dist + beta*norm_time + gamma*congestion + delta*risk` |
| `distance_km` | Physical route distance in kilometres |
| `path_length` | Number of nodes in the returned path |
| `visited_nodes` | Nodes in `result.visited_order` |
| `expanded_nodes` | EXPAND step count from `result.steps` |
| `peak_memory_kb` | Peak RSS from `tracemalloc` (measured in a separate call) |
| `success` | True only if result.success=True AND route validated (start, goal, all edges exist) |

## Random Seed Policy

- **Deterministic algorithms** (BFS, DFS, UCS, A\*, Beam Search): No seed needed. Runs are identical.
- **GA**: `random.seed(seed)` applied in the benchmark adapter before each call. Seeds: 0–29.
- **SA**: `random.seed(seed)` applied in the benchmark adapter before each call. Seeds: 0–29.
- Seeds are set **only in the benchmark layer**, never inside the algorithm implementations.

## Cost Formula

```
Edge cost = alpha * norm_distance
          + beta  * norm_travel_time
          + gamma * congestion
          + delta * risk

Defaults (from src/constants.py):
  alpha = 0.25  (distance weight)
  beta  = 0.45  (travel time weight)
  gamma = 0.20  (congestion weight)
  delta = 0.10  (risk weight)

norm_distance    = edge.distance / graph.max_distance
norm_travel_time = edge.travel_time / graph.max_time
```

All algorithms are evaluated using this same canonical formula regardless of what cost they internally report.

## Warmup Policy

Each (algorithm, scenario) pair receives **2 warmup runs** before measurement begins. Warmup results are discarded. Purpose: eliminate Python import caching, JIT warmup, and one-time initialization overhead.

## Dataset

Default: `_map_data.json` (20 nodes — small curated graph of central HCMC landmarks)

Alternate: any `.json` file in the `data/` directory (OSM data for HCMC districts).

All algorithms use the same loaded graph instance (no reload between algorithms).

## Known Issues / Findings

See `results/BENCHMARK_FINDINGS.md` after running the benchmark.

Known pre-identified issue:
- **Beam Search** (`beam_search.py` lines 75, 110): calls `edge.calculate_cost(mode=mode)` but `Edge.calculate_cost()` only accepts `(alpha, beta, gamma, delta)`. This will raise `TypeError`. The implementation is NOT modified by this benchmark.
