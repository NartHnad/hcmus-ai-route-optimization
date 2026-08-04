import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import src.algorithms.route_comparison as route_comparison_module
from src.algorithms.algorithms import run_algorithm
from src.algorithms.route_comparison import (
    AlternativeRouteSelector,
    build_route_comparison,
    calculate_route_metrics,
    compare_routes,
    optimality_statement,
)
from src.gui.delivery_panel import RouteComparisonPanel
from src.gui.main_window import SearchWorker
from src.models.models import (
    ComparisonMode,
    Edge,
    Graph,
    Node,
    RouteMetrics,
    SearchResult,
)


BFS = "Breadth-First Search (BFS)"
DFS = "Depth-First Search (DFS)"
UCS = "Uniform Cost Search (UCS)"
ASTAR = "A* Search"


def make_graph(node_ids, edges):
    graph = Graph()
    for index, node_id in enumerate(node_ids):
        graph.add_node(Node(node_id, node_id, 10.0 + index * 0.001, 106.0))
    for edge_data in edges:
        graph.add_edge(
            Edge(
                edge_data[0],
                edge_data[1],
                distance=edge_data[2],
                travel_time=edge_data[3],
                road_type=edge_data[4],
                is_one_way=True,
                congestion=edge_data[5],
                risk=edge_data[6],
                note=edge_data[7],
            )
        )
    return graph


def comparison_graph():
    # BFS prefers the two-edge B route; UCS prefers the cheaper three-edge C-D route.
    return make_graph(
        ("A", "B", "C", "D", "G"),
        (
            ("A", "B", 4.0, 2.0, "primary", 2, 0, "Đường nhanh 1"),
            ("B", "G", 4.0, 2.0, "primary", 2, 0, "Đường nhanh 2"),
            ("A", "C", 1.0, 1.0, "local", 0, 0, "Đường vắng 1"),
            ("C", "D", 1.0, 1.0, "local", 0, 0, "Đường vắng 2"),
            ("D", "G", 1.0, 1.0, "local", 0, 0, "Đường vắng 3"),
        ),
    )


def test_calculate_route_metrics_uses_one_canonical_cost_function():
    graph = make_graph(
        ("A", "B", "C"),
        (
            ("A", "B", 2.0, 5.0, "primary", 4, 1, "Đường Một"),
            ("B", "C", 3.0, 4.0, "local", 1, 2, "Đường Hai"),
        ),
    )

    metrics = calculate_route_metrics(graph, ["A", "B", "C"])

    assert metrics.valid
    assert metrics.total_distance == pytest.approx(5.0)
    assert metrics.total_time == pytest.approx(9.0)
    assert metrics.congestion_penalty == pytest.approx(5.0)
    assert metrics.total_cost == pytest.approx(22.0)
    assert [segment.road_name for segment in metrics.segments] == [
        "Đường Một",
        "Đường Hai",
    ]


def test_different_algorithms_runs_second_algorithm_on_same_request(monkeypatch):
    graph = comparison_graph()
    primary = run_algorithm(BFS, graph, "A", "G")
    calls = []
    real_runner = run_algorithm

    def tracking_runner(name, supplied_graph, start, goal):
        calls.append((name, supplied_graph, start, goal))
        return real_runner(name, supplied_graph, start, goal)

    monkeypatch.setattr(route_comparison_module, "run_algorithm", tracking_runner)
    original_adjacency = {
        node_id: tuple(edges)
        for node_id, edges in graph.adjacency_list.items()
    }

    comparison = build_route_comparison(
        graph,
        primary,
        BFS,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=UCS,
        start_id="A",
        goal_id="G",
    )

    assert calls == [(UCS, graph, "A", "G")]
    assert comparison.mode is ComparisonMode.DIFFERENT_ALGORITHMS
    assert comparison.selected.path == ["A", "B", "G"]
    assert comparison.alternative.path == ["A", "C", "D", "G"]
    assert comparison.selected.total_cost == pytest.approx(16.0)
    assert comparison.alternative.total_cost == pytest.approx(6.0)
    assert comparison.winners["total_cost"] == "alternative"
    assert original_adjacency == {
        node_id: tuple(edges)
        for node_id, edges in graph.adjacency_list.items()
    }


def test_same_algorithm_alternative_reruns_same_public_algorithm(monkeypatch):
    graph = comparison_graph()
    primary = run_algorithm(BFS, graph, "A", "G")
    calls = []
    real_runner = run_algorithm

    def tracking_runner(name, supplied_graph, start, goal):
        calls.append((name, supplied_graph, start, goal))
        return real_runner(name, supplied_graph, start, goal)

    monkeypatch.setattr(route_comparison_module, "run_algorithm", tracking_runner)
    edge_count_before = sum(len(edges) for edges in graph.adjacency_list.values())

    comparison = build_route_comparison(
        graph,
        primary,
        BFS,
        mode=ComparisonMode.SAME_ALGORITHM_ALTERNATIVE,
        start_id="A",
        goal_id="G",
    )

    assert calls
    assert {call[0] for call in calls} == {BFS}
    assert all(call[2:] == ("A", "G") for call in calls)
    assert all(call[1].nodes is graph.nodes for call in calls)
    assert comparison.comparison_algorithm == BFS
    assert comparison.selected.path == ["A", "B", "G"]
    assert comparison.alternative.path == ["A", "C", "D", "G"]
    assert comparison.alternative.path != comparison.selected.path
    assert sum(len(edges) for edges in graph.adjacency_list.values()) == edge_count_before


def test_alternative_selector_returns_none_when_only_one_route_exists():
    graph = make_graph(
        ("A", "B", "G"),
        (
            ("A", "B", 1.0, 1.0, "local", 0, 0, "AB"),
            ("B", "G", 1.0, 1.0, "local", 0, 0, "BG"),
        ),
    )

    alternative = AlternativeRouteSelector().select(
        graph,
        ["A", "B", "G"],
        BFS,
    )

    assert alternative is None


def test_different_algorithms_mode_rejects_same_algorithm():
    graph = comparison_graph()
    primary = run_algorithm(BFS, graph, "A", "G")

    with pytest.raises(ValueError, match="requires two algorithms"):
        build_route_comparison(
            graph,
            primary,
            BFS,
            mode=ComparisonMode.DIFFERENT_ALGORITHMS,
            comparison_algorithm=BFS,
            start_id="A",
            goal_id="G",
        )


def test_secondary_algorithm_uses_requested_start_goal_when_primary_fails(monkeypatch):
    graph = comparison_graph()
    primary = SearchResult(success=False, message="primary failed")
    calls = []

    def fake_runner(name, supplied_graph, start, goal):
        calls.append((name, supplied_graph, start, goal))
        return SearchResult(path=["A", "C", "D", "G"], success=True)

    monkeypatch.setattr(route_comparison_module, "run_algorithm", fake_runner)

    comparison = build_route_comparison(
        graph,
        primary,
        DFS,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=UCS,
        start_id="A",
        goal_id="G",
    )

    assert calls == [(UCS, graph, "A", "G")]
    assert not comparison.selected.valid
    assert comparison.alternative.valid
    assert "không trả về tuyến chính hợp lệ" in comparison.explanation.text


def test_comparison_serialization_exposes_mode_and_both_algorithms():
    graph = comparison_graph()
    first = calculate_route_metrics(graph, ["A", "B", "G"])
    second = calculate_route_metrics(graph, ["A", "C", "D", "G"])
    comparison = compare_routes(
        first,
        second,
        BFS,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=UCS,
        graph=graph,
    )

    payload = comparison.to_dict()
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)

    assert payload["mode"] == "different_algorithms"
    assert payload["primary_algorithm"] == BFS
    assert payload["comparison_algorithm"] == UCS
    assert payload["cost_mode"] == "optimal"
    assert payload["route_a"] == payload["selected"]
    assert payload["route_b"] == payload["alternative"]
    assert encoded


def test_explanation_is_concise_recommends_by_cost_and_is_cautious():
    graph = comparison_graph()
    first = calculate_route_metrics(graph, ["A", "B", "G"])
    second = calculate_route_metrics(graph, ["A", "C", "D", "G"])

    comparison = compare_routes(
        first,
        second,
        ASTAR,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=UCS,
        graph=graph,
    )
    text = comparison.explanation.text

    assert "Route A dùng A* Search" in text
    assert "Route B dùng Uniform Cost Search (UCS)" in text
    assert "Gợi ý theo total cost: chọn Route B" in text
    assert "chưa chứng minh" in text
    assert "UCS bảo đảm tối ưu" in text
    assert "A → B → G" not in text


def test_high_congestion_segments_are_named_in_explanation():
    graph = make_graph(
        ("A", "B", "C", "G"),
        (
            ("A", "B", 1.0, 1.0, "local", 4, 0, "Đường Đông"),
            ("B", "G", 1.0, 1.0, "local", 0, 0, "BG"),
            ("A", "C", 1.0, 1.0, "local", 0, 0, "AC"),
            ("C", "G", 1.0, 1.0, "local", 0, 0, "CG"),
        ),
    )
    selected = calculate_route_metrics(graph, ["A", "B", "G"])
    alternative = calculate_route_metrics(graph, ["A", "C", "G"])

    comparison = compare_routes(selected, alternative, DFS, graph=graph)

    assert [segment.congestion for segment in selected.high_congestion_segments] == [4]
    assert "A → B (Đường Đông), mức 4" in comparison.explanation.text


def test_optimality_claim_depends_on_algorithm_conditions():
    graph = comparison_graph()
    negative_graph = make_graph(
        ("A", "G"),
        (("A", "G", -5.0, 0.0, "local", 0, 0, "negative"),),
    )

    assert "bảo đảm tối ưu" in optimality_statement(UCS, graph)
    assert "không được bảo đảm" in optimality_statement(UCS, negative_graph)
    assert "không bảo đảm" in optimality_statement(DFS, graph)
    assert "chưa chứng minh" in optimality_statement(ASTAR, graph)
    assert "không bảo đảm" in optimality_statement(BFS, graph)


def test_start_equals_goal_is_valid_but_has_no_alternative():
    graph = make_graph(("A",), ())
    selected = calculate_route_metrics(graph, ["A"])

    alternative = AlternativeRouteSelector().select(graph, ["A"], BFS)

    assert selected.valid
    assert selected.total_cost == 0.0
    assert selected.segments == []
    assert alternative is None


def test_build_comparison_preserves_algorithm_reported_cost():
    graph = comparison_graph()
    result = SearchResult(
        path=["A", "B", "G"],
        total_cost=999.0,
        success=True,
        visited_order=["A", "B", "G"],
    )

    comparison = build_route_comparison(
        graph,
        result,
        BFS,
        mode=ComparisonMode.SAME_ALGORITHM_ALTERNATIVE,
    )

    assert result.total_cost == 999.0
    assert comparison.selected.total_cost == pytest.approx(16.0)
    assert result.to_dict()["comparison"]["mode"] == "same_algorithm_alternative"


def test_search_worker_builds_requested_comparison_mode():
    graph = comparison_graph()
    worker = SearchWorker(
        BFS,
        graph,
        "A",
        "G",
        comparison_mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=UCS,
    )
    completed = []
    failed = []
    worker.completed.connect(lambda result, runtime: completed.append((result, runtime)))
    worker.failed.connect(failed.append)

    worker.run()

    assert not failed
    assert len(completed) == 1
    result, runtime = completed[0]
    assert runtime >= 0.0
    assert result.comparison.mode is ComparisonMode.DIFFERENT_ALGORITHMS
    assert result.comparison.comparison_algorithm == UCS


def test_comparison_panel_switches_between_both_modes():
    app = QApplication.instance() or QApplication([])
    graph = comparison_graph()
    selected = calculate_route_metrics(graph, ["A", "B", "G"])
    alternative = calculate_route_metrics(graph, ["A", "C", "D", "G"])
    comparison = compare_routes(
        selected,
        alternative,
        BFS,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=UCS,
        graph=graph,
    )
    panel = RouteComparisonPanel([BFS, UCS, DFS])

    panel.set_comparison(comparison)

    assert panel.current_mode() is ComparisonMode.DIFFERENT_ALGORITHMS
    assert panel.algorithm_combo.isEnabled()
    assert "Route A" in panel.selected_route_label.text()
    assert "Route B" in panel.alternative_route_label.text()

    same_index = panel.mode_combo.findData(
        ComparisonMode.SAME_ALGORITHM_ALTERNATIVE.value
    )
    panel.mode_combo.setCurrentIndex(same_index)

    assert panel.current_mode() is ComparisonMode.SAME_ALGORITHM_ALTERNATIVE
    assert not panel.algorithm_combo.isEnabled()
    assert panel.metrics_table.horizontalHeaderItem(1).text() == "Selected"
    assert panel.metrics_table.horizontalHeaderItem(2).text() == "Alternative"
    panel.deleteLater()
    app.processEvents()


def test_panel_handles_missing_second_route_without_crashing():
    app = QApplication.instance() or QApplication([])
    selected = RouteMetrics(
        path=["A", "G"],
        total_distance=1.0,
        total_time=2.0,
        congestion_penalty=0.0,
        total_cost=3.0,
        valid=True,
    )
    comparison = compare_routes(selected, None, BFS)
    panel = RouteComparisonPanel([BFS, UCS])

    panel.set_comparison(comparison)

    assert panel.status_label.text() == "Second route not found"
    assert "Not found" in panel.alternative_route_label.text()
    assert "Không tìm thấy Alternative hợp lệ" in panel.explanation_label.text()
    panel.deleteLater()
    app.processEvents()


def test_panel_can_request_another_mode_after_recompute_error():
    app = QApplication.instance() or QApplication([])
    panel = RouteComparisonPanel([BFS, UCS])
    panel.configure(BFS)
    panel.set_error("temporary failure")
    requests = []
    panel.comparison_requested.connect(
        lambda mode, algorithm: requests.append((mode, algorithm))
    )

    same_index = panel.mode_combo.findData(
        ComparisonMode.SAME_ALGORITHM_ALTERNATIVE.value
    )
    panel.mode_combo.setCurrentIndex(same_index)

    assert requests == [
        (ComparisonMode.SAME_ALGORITHM_ALTERNATIVE.value, BFS)
    ]
    panel.deleteLater()
    app.processEvents()
