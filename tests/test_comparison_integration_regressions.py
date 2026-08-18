import os
import random

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import src.gui.main_window as main_window_module
from src.algorithms.route_comparison import build_route_comparison
from src.gui.main_window import SearchWorker
from src.models.models import ComparisonMode, Edge, Graph, Node, RouteRequest, SearchResult


BFS = "Breadth-First Search (BFS)"


def _graph():
    graph = Graph()
    graph.add_node(Node("A", "A", 10.0, 106.0))
    graph.add_node(Node("B", "B", 10.001, 106.0))
    graph.add_edge(
        Edge(
            "A",
            "B",
            distance=1.0,
            travel_time=1.0,
            road_type="local",
            is_one_way=True,
            congestion=0.0,
            risk=0.0,
        )
    )
    return graph


def _multi_graph():
    graph = Graph()
    node_ids = ("A", "B", "C", "D")
    for index, node_id in enumerate(node_ids):
        graph.add_node(Node(node_id, node_id, 10.0 + index * 0.001, 106.0))
    for from_node in node_ids:
        for to_node in node_ids:
            if from_node != to_node:
                graph.add_edge(
                    Edge(
                        from_node,
                        to_node,
                        distance=1.0,
                        travel_time=1.0,
                        road_type="local",
                        is_one_way=True,
                    )
                )
    return graph


def test_legacy_three_argument_search_worker_does_not_run_comparison(monkeypatch):
    def unexpected_comparison(*args, **kwargs):
        raise AssertionError("legacy SearchWorker unexpectedly ran comparison")

    monkeypatch.setattr(
        main_window_module,
        "build_route_comparison",
        unexpected_comparison,
    )
    worker = SearchWorker(BFS, _graph(), RouteRequest("A", ("B",)))
    completed = []
    failed = []
    worker.completed.connect(lambda result, runtime: completed.append(result))
    worker.failed.connect(failed.append)

    worker.run()

    assert not failed
    assert len(completed) == 1
    assert completed[0].path == ["A", "B"]
    assert completed[0].comparison is None
    assert not hasattr(completed[0], "comparison_error")


def test_secondary_simulated_annealing_restores_shared_random_state():
    graph = _multi_graph()
    request = RouteRequest("A", ("B", "C", "D"))
    primary = SearchResult(
        path=["A", "B", "C", "D"],
        success=True,
        total_cost=3.0,
    )
    random.seed(20260818)
    state_before = random.getstate()

    build_route_comparison(
        graph,
        primary,
        "Primary route",
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm="Simulated Annealing (SA)",
        route_request=request,
    )

    assert random.getstate() == state_before
