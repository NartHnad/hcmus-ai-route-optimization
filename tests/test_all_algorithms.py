import csv
import math
import random
import time
from pathlib import Path

import networkx as nx
import pytest

from src.algorithms.algorithms import (
    get_algorithms,
    run_algorithm,
    run_multi_location_algorithm,
)
from src.models.graph_factory import build_graph
from src.models.models import SearchResult, StepType


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REAL_DATASET_PATH = PROJECT_ROOT / "data" / "district5_subgraph_50nodes.json"
REAL_DISTRICT = "Quận 5"
REPORT_PATH = (
    PROJECT_ROOT
    / "benchmarks"
    / "results"
    / "algorithm_test_results_district5.csv"
)
REPORT_FIELDS = (
    "mode",
    "scenario",
    "dataset",
    "district",
    "graph_nodes",
    "graph_edges",
    "algorithm",
    "status",
    "success",
    "path_valid",
    "graph_unchanged",
    "start",
    "start_name",
    "goals",
    "goal_names",
    "goal_visit_order",
    "path",
    "path_names",
    "total_cost",
    "runtime_ms",
    "step_count",
    "expanded_steps",
    "visited_nodes",
    "message",
)

EXPECTED_SINGLE_ALGORITHMS = (
    "A* Search",
    "Beam Search Algorithm",
    "Bidirectional Search (UCS)",
    "Breadth-First Search (BFS)",
    "Depth-First Search (DFS)",
    "Genetic Algorithm (GA)",
    "Uniform Cost Search (UCS)",
)

EXPECTED_MULTI_ALGORITHMS = (
    "Genetic Algorithm (GA)",
    "Mock Multi-location Search",
    "Nearest Neighbor + 2-Opt",
    "Simulated Annealing (SA)",
)


def _load_real_district_graph():
    """Load the fixed District 5 road dataset used by every algorithm test."""
    assert REAL_DATASET_PATH.is_file(), f"Missing real dataset: {REAL_DATASET_PATH}"
    return build_graph(str(REAL_DATASET_PATH))


def _natural_node_key(node_id):
    text = str(node_id)
    return len(text), text


def _select_real_scenario(graph):
    """Choose reproducible, mutually reachable endpoints from the real road graph."""
    directed_graph = nx.DiGraph()
    directed_graph.add_nodes_from(graph.nodes)
    directed_graph.add_edges_from(
        (source, edge.to_node)
        for source, edges in graph.adjacency_list.items()
        for edge in edges
    )

    components = sorted(
        nx.strongly_connected_components(directed_graph),
        key=lambda component: (
            -len(component),
            tuple(sorted(component, key=_natural_node_key)),
        ),
    )
    largest_component = components[0]
    assert len(largest_component) >= 4

    start = min(largest_component, key=_natural_node_key)
    component_graph = directed_graph.subgraph(largest_component)
    hop_distances = nx.single_source_shortest_path_length(component_graph, start)
    farthest_nodes = sorted(
        (node for node in largest_component if node != start),
        key=lambda node: (-hop_distances[node], _natural_node_key(node)),
    )
    single_goal = farthest_nodes[0]
    multi_goals = tuple(farthest_nodes[:3])
    return start, single_goal, multi_goals


def _edge_signature(graph):
    return tuple(
        sorted(
            (
                edge.from_node,
                edge.to_node,
                edge.distance,
                edge.travel_time,
                edge.congestion,
                edge.risk,
            )
            for edges in graph.adjacency_list.values()
            for edge in edges
        )
    )


def _run_with_fixed_random_seed(callback):
    """Keep stochastic tests reproducible without leaking random state to other tests."""
    previous_state = random.getstate()
    try:
        random.seed(20260818)
        return callback()
    finally:
        random.setstate(previous_state)


def _assert_successful_result(graph, result, start, required_nodes):
    assert isinstance(result, SearchResult)
    assert result.success, result.message
    assert result.path
    assert result.path[0] == start
    assert set(required_nodes).issubset(result.path)
    assert math.isfinite(result.total_cost)
    assert result.total_cost >= 0.0
    assert result.steps
    assert result.steps[-1].step_type is StepType.FINISH

    for source, target in zip(result.path, result.path[1:]):
        assert graph.get_edge(source, target) is not None


def _measure_algorithm(callback):
    started = time.perf_counter()
    try:
        result = callback()
        error = ""
    except Exception as exc:  # Keep a CSV row even when an algorithm crashes.
        result = None
        error = f"{type(exc).__name__}: {exc}"
    runtime_ms = (time.perf_counter() - started) * 1000.0
    return result, runtime_ms, error


def _has_valid_path(graph, result, start, required_nodes):
    if not isinstance(result, SearchResult) or not result.path:
        return False
    if result.path[0] != start or not set(required_nodes).issubset(result.path):
        return False
    return all(
        graph.get_edge(source, target) is not None
        for source, target in zip(result.path, result.path[1:])
    )


def _has_success_contract(graph, result, start, required_nodes):
    return bool(
        isinstance(result, SearchResult)
        and result.success
        and _has_valid_path(graph, result, start, required_nodes)
        and math.isfinite(result.total_cost)
        and result.total_cost >= 0.0
        and result.steps
        and result.steps[-1].step_type is StepType.FINISH
    )


def _append_report_row(
    rows,
    *,
    mode,
    scenario,
    algorithm_name,
    graph,
    graph_before,
    result,
    runtime_ms,
    error,
    start,
    goals,
    scenario_valid,
):
    path = list(getattr(result, "path", []) or [])
    goal_order = list(getattr(result, "goal_visit_order", []) or [])
    steps = list(getattr(result, "steps", []) or [])
    visited_order = list(getattr(result, "visited_order", []) or [])
    graph_unchanged = _edge_signature(graph) == graph_before

    rows.append(
        {
            "mode": mode,
            "scenario": scenario,
            "dataset": REAL_DATASET_PATH.name,
            "district": REAL_DISTRICT,
            "graph_nodes": len(graph.nodes),
            "graph_edges": sum(len(edges) for edges in graph.adjacency_list.values()),
            "algorithm": algorithm_name,
            "status": "ERROR" if error else ("PASS" if scenario_valid else "FAIL"),
            "success": bool(getattr(result, "success", False)),
            "path_valid": _has_valid_path(graph, result, start, goals),
            "graph_unchanged": graph_unchanged,
            "start": start,
            "start_name": graph.nodes[start].name,
            "goals": " | ".join(goals),
            "goal_names": " | ".join(graph.nodes[node].name for node in goals),
            "goal_visit_order": " | ".join(goal_order),
            "path": " -> ".join(path),
            "path_names": " -> ".join(graph.nodes[node].name for node in path),
            "total_cost": getattr(result, "total_cost", ""),
            "runtime_ms": round(runtime_ms, 6),
            "step_count": len(steps),
            "expanded_steps": sum(
                getattr(step, "step_type", None) is StepType.EXPAND for step in steps
            ),
            "visited_nodes": len(visited_order),
            "message": error or str(getattr(result, "message", "")),
        }
    )


@pytest.fixture(scope="module")
def algorithm_csv_rows():
    rows = []
    yield rows

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ordered_rows = sorted(
        rows,
        key=lambda row: (row["mode"], row["scenario"], row["algorithm"]),
    )
    with REPORT_PATH.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(ordered_rows)
    print(f"\nAlgorithm CSV report: {REPORT_PATH}")


def test_algorithm_registries_include_every_supported_algorithm():
    assert tuple(get_algorithms("single")) == EXPECTED_SINGLE_ALGORITHMS
    assert tuple(get_algorithms("multi")) == EXPECTED_MULTI_ALGORITHMS


def test_real_district_dataset_provides_a_shared_reachable_scenario():
    graph = _load_real_district_graph()
    start, single_goal, multi_goals = _select_real_scenario(graph)

    assert len(graph.nodes) == 50
    assert sum(len(edges) for edges in graph.adjacency_list.values()) == 173
    assert start == "366386196"
    assert single_goal == "5674570742"
    assert multi_goals == ("5674570742", "5813971157", "5813971180")


@pytest.mark.parametrize("algorithm_name", EXPECTED_SINGLE_ALGORITHMS)
def test_every_single_route_algorithm_runs_through_public_dispatcher(
    algorithm_name, algorithm_csv_rows
):
    graph = _load_real_district_graph()
    start, single_goal, _multi_goals = _select_real_scenario(graph)
    graph_before = _edge_signature(graph)

    result, runtime_ms, error = _measure_algorithm(
        lambda: _run_with_fixed_random_seed(
            lambda: run_algorithm(algorithm_name, graph, start, single_goal)
        )
    )
    scenario_valid = bool(
        not error
        and _has_success_contract(graph, result, start, (single_goal,))
        and result.path[-1] == single_goal
        and _edge_signature(graph) == graph_before
    )
    _append_report_row(
        algorithm_csv_rows,
        mode="single",
        scenario="point_to_point",
        algorithm_name=algorithm_name,
        graph=graph,
        graph_before=graph_before,
        result=result,
        runtime_ms=runtime_ms,
        error=error,
        start=start,
        goals=(single_goal,),
        scenario_valid=scenario_valid,
    )

    assert not error, error
    _assert_successful_result(graph, result, start, (single_goal,))
    assert result.path[-1] == single_goal
    assert _edge_signature(graph) == graph_before


@pytest.mark.parametrize("algorithm_name", EXPECTED_MULTI_ALGORITHMS)
def test_every_multi_location_algorithm_visits_all_goals(
    algorithm_name, algorithm_csv_rows
):
    graph = _load_real_district_graph()
    start, _single_goal, goals = _select_real_scenario(graph)
    graph_before = _edge_signature(graph)

    result, runtime_ms, error = _measure_algorithm(
        lambda: _run_with_fixed_random_seed(
            lambda: run_multi_location_algorithm(
                algorithm_name, graph, start, goals
            )
        )
    )
    scenario_valid = bool(
        not error
        and _has_success_contract(graph, result, start, goals)
        and len(result.goal_visit_order) == len(goals)
        and set(result.goal_visit_order) == set(goals)
        and _edge_signature(graph) == graph_before
    )
    _append_report_row(
        algorithm_csv_rows,
        mode="multi",
        scenario="optimize_goal_order",
        algorithm_name=algorithm_name,
        graph=graph,
        graph_before=graph_before,
        result=result,
        runtime_ms=runtime_ms,
        error=error,
        start=start,
        goals=goals,
        scenario_valid=scenario_valid,
    )

    assert not error, error
    _assert_successful_result(graph, result, start, goals)
    assert len(result.goal_visit_order) == len(goals)
    assert set(result.goal_visit_order) == set(goals)
    assert _edge_signature(graph) == graph_before


@pytest.mark.parametrize("algorithm_name", EXPECTED_MULTI_ALGORITHMS)
def test_every_multi_location_algorithm_respects_order_and_round_trip(
    algorithm_name, algorithm_csv_rows
):
    graph = _load_real_district_graph()
    start, _single_goal, goals = _select_real_scenario(graph)
    graph_before = _edge_signature(graph)

    result, runtime_ms, error = _measure_algorithm(
        lambda: _run_with_fixed_random_seed(
            lambda: run_multi_location_algorithm(
                algorithm_name,
                graph,
                start,
                goals,
                respect_goal_order=True,
                return_to_start=True,
            )
        )
    )
    scenario_valid = bool(
        not error
        and _has_success_contract(graph, result, start, goals)
        and result.goal_visit_order == list(goals)
        and result.path[-1] == start
        and _edge_signature(graph) == graph_before
    )
    _append_report_row(
        algorithm_csv_rows,
        mode="multi",
        scenario="ordered_round_trip",
        algorithm_name=algorithm_name,
        graph=graph,
        graph_before=graph_before,
        result=result,
        runtime_ms=runtime_ms,
        error=error,
        start=start,
        goals=goals,
        scenario_valid=scenario_valid,
    )

    assert not error, error
    _assert_successful_result(graph, result, start, goals)
    assert result.goal_visit_order == list(goals)
    assert result.path[-1] == start
    assert _edge_signature(graph) == graph_before
