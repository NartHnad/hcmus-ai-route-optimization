import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import src.algorithms.route_comparison as route_comparison_module
from src.algorithms.algorithms import run_algorithm, run_route_request
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
    RouteRequest,
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
    # BFS prefers the two-edge B route; UCS prefers the cheaper three-edge route.
    return make_graph(
        ("A", "B", "C", "D", "G"),
        (
            ("A", "B", 4.0, 2.0, "primary", 0.5, 0.0, "Đường nhanh 1"),
            ("B", "G", 4.0, 2.0, "primary", 0.5, 0.0, "Đường nhanh 2"),
            ("A", "C", 1.0, 1.0, "local", 0.0, 0.0, "Đường vắng 1"),
            ("C", "D", 1.0, 1.0, "local", 0.0, 0.0, "Đường vắng 2"),
            ("D", "G", 1.0, 1.0, "local", 0.0, 0.0, "Đường vắng 3"),
        ),
    )


def test_calculate_route_metrics_uses_current_edge_cost_semantics():
    graph = make_graph(
        ("A", "B", "C"),
        (
            ("A", "B", 2.0, 5.0, "primary", 0.75, 0.1, "Đường Một"),
            ("B", "C", 3.0, 4.0, "local", 0.25, 0.2, "Đường Hai"),
        ),
    )

    metrics = calculate_route_metrics(graph, ["A", "B", "C"])

    assert metrics.valid
    assert metrics.total_distance == pytest.approx(5.0)
    assert metrics.total_time == pytest.approx(9.0)
    assert metrics.congestion_penalty == pytest.approx(1.0)
    assert metrics.total_cost == pytest.approx(14.0)
    assert [segment.road_name for segment in metrics.segments] == [
        "Đường Một",
        "Đường Hai",
    ]


def test_different_algorithms_runs_same_current_route_request(monkeypatch):
    graph = comparison_graph()
    request = RouteRequest("A", ("G",))
    primary = run_route_request(BFS, graph, request)
    calls = []
    real_runner = run_route_request

    def tracking_runner(name, supplied_graph, supplied_request):
        calls.append((name, supplied_graph, supplied_request))
        return real_runner(name, supplied_graph, supplied_request)

    monkeypatch.setattr(route_comparison_module, "run_route_request", tracking_runner)
    original_adjacency = {
        node_id: tuple(edges) for node_id, edges in graph.adjacency_list.items()
    }

    comparison = build_route_comparison(
        graph,
        primary,
        BFS,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=UCS,
        route_request=request,
    )

    assert calls == [(UCS, graph, request)]
    assert comparison.mode is ComparisonMode.DIFFERENT_ALGORITHMS
    assert comparison.selected.path == ["A", "B", "G"]
    assert comparison.alternative.path == ["A", "C", "D", "G"]
    assert comparison.selected.total_cost == pytest.approx(12.0)
    assert comparison.alternative.total_cost == pytest.approx(6.0)
    assert comparison.winners["total_cost"] == "alternative"
    assert original_adjacency == {
        node_id: tuple(edges) for node_id, edges in graph.adjacency_list.items()
    }


def test_same_algorithm_alternative_uses_route_request_dispatch(monkeypatch):
    graph = comparison_graph()
    request = RouteRequest("A", ("G",))
    primary = run_route_request(BFS, graph, request)
    calls = []
    real_runner = run_route_request

    def tracking_runner(name, supplied_graph, supplied_request):
        calls.append((name, supplied_graph, supplied_request))
        return real_runner(name, supplied_graph, supplied_request)

    monkeypatch.setattr(route_comparison_module, "run_route_request", tracking_runner)
    edge_count_before = sum(len(edges) for edges in graph.adjacency_list.values())

    comparison = build_route_comparison(
        graph,
        primary,
        BFS,
        mode=ComparisonMode.SAME_ALGORITHM_ALTERNATIVE,
        route_request=request,
    )

    assert calls
    assert {call[0] for call in calls} == {BFS}
    assert all(call[2] is request for call in calls)
    assert all(call[1].nodes is graph.nodes for call in calls)
    assert comparison.comparison_algorithm == BFS
    assert comparison.selected.path == ["A", "B", "G"]
    assert comparison.alternative.path == ["A", "C", "D", "G"]
    assert sum(len(edges) for edges in graph.adjacency_list.values()) == edge_count_before


def test_multi_location_comparison_preserves_immutable_request(monkeypatch):
    graph = make_graph(
        ("A", "B", "C", "D", "G"),
        (
            ("A", "B", 1.0, 1.0, "local", 0.0, 0.0, "AB"),
            ("B", "C", 1.0, 1.0, "local", 0.0, 0.0, "BC"),
            ("C", "G", 1.0, 1.0, "local", 0.0, 0.0, "CG"),
            ("A", "D", 2.0, 1.0, "local", 0.0, 0.0, "AD"),
            ("D", "C", 2.0, 1.0, "local", 0.0, 0.0, "DC"),
        ),
    )
    request = RouteRequest(
        "A",
        ("C", "G"),
        respect_goal_order=True,
        return_to_start=False,
    )
    primary = SearchResult(path=["A", "B", "C", "G"], success=True)
    calls = []

    def fake_runner(name, supplied_graph, supplied_request):
        calls.append((name, supplied_graph, supplied_request))
        return SearchResult(path=["A", "D", "C", "G"], success=True)

    monkeypatch.setattr(route_comparison_module, "run_route_request", fake_runner)

    comparison = build_route_comparison(
        graph,
        primary,
        "Genetic Algorithm (GA)",
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm="Simulated Annealing (SA)",
        route_request=request,
    )

    assert calls == [("Simulated Annealing (SA)", graph, request)]
    assert comparison.alternative.path == ["A", "D", "C", "G"]
    assert request.delivery_nodes == ("C", "G")
    assert request.respect_goal_order


def test_alternative_selector_returns_none_when_only_one_route_exists():
    graph = make_graph(
        ("A", "B", "G"),
        (
            ("A", "B", 1.0, 1.0, "local", 0.0, 0.0, "AB"),
            ("B", "G", 1.0, 1.0, "local", 0.0, 0.0, "BG"),
        ),
    )

    alternative = AlternativeRouteSelector().select(graph, ["A", "B", "G"], BFS)

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


def test_secondary_algorithm_uses_request_when_primary_has_no_path(monkeypatch):
    graph = comparison_graph()
    request = RouteRequest("A", ("G",))
    primary = SearchResult(success=False, message="primary failed")
    calls = []

    def fake_runner(name, supplied_graph, supplied_request):
        calls.append((name, supplied_graph, supplied_request))
        return SearchResult(path=["A", "C", "D", "G"], success=True)

    monkeypatch.setattr(route_comparison_module, "run_route_request", fake_runner)

    comparison = build_route_comparison(
        graph,
        primary,
        DFS,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=UCS,
        route_request=request,
    )

    assert calls == [(UCS, graph, request)]
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
    assert payload["cost_mode"] == "current_composite"
    assert payload["route_a"] == payload["selected"]
    assert payload["route_b"] == payload["alternative"]
    assert encoded


def test_explanation_separates_distance_time_and_current_total_cost():
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

    assert "Khoảng cách" in text
    assert "Thời gian di chuyển" in text
    assert "Total cost hiện tại" in text
    assert "Gợi ý theo total cost: chọn Route B" in text
    assert "không tự khẳng định" in text
    assert "UCS bảo đảm tối ưu" in text
    assert "A → B → G" not in text


def test_heavy_congestion_uses_current_zero_to_one_threshold():
    graph = make_graph(
        ("A", "B", "C", "G"),
        (
            ("A", "B", 1.0, 1.0, "local", 0.75, 0.0, "Đường Đông"),
            ("B", "G", 1.0, 1.0, "local", 0.0, 0.0, "BG"),
            ("A", "C", 1.0, 1.0, "local", 0.5, 0.0, "AC"),
            ("C", "G", 1.0, 1.0, "local", 0.0, 0.0, "CG"),
        ),
    )
    selected = calculate_route_metrics(graph, ["A", "B", "G"])
    alternative = calculate_route_metrics(graph, ["A", "C", "G"])

    comparison = compare_routes(selected, alternative, DFS, graph=graph)

    assert [segment.congestion for segment in selected.high_congestion_segments] == [
        0.75
    ]
    assert "A → B (Đường Đông), mức 0.75" in comparison.explanation.text


def test_optimality_claims_are_cautious_and_condition_based():
    graph = comparison_graph()
    negative_graph = make_graph(
        ("A", "G"),
        (("A", "G", -5.0, 0.0, "local", 0.0, 0.0, "negative"),),
    )

    assert "bảo đảm tối ưu" in optimality_statement(UCS, graph)
    assert "không được bảo đảm" in optimality_statement(UCS, negative_graph)
    assert "không bảo đảm" in optimality_statement(DFS, graph)
    assert "không tự khẳng định" in optimality_statement(ASTAR, graph)
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
    assert comparison.selected.total_cost == pytest.approx(12.0)
    assert result.to_dict()["comparison"]["mode"] == "same_algorithm_alternative"


def test_search_worker_builds_requested_comparison_mode():
    graph = comparison_graph()
    request = RouteRequest("A", ("G",))
    worker = SearchWorker(
        BFS,
        graph,
        request,
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


def test_search_worker_keeps_primary_result_when_comparison_fails():
    graph = comparison_graph()
    request = RouteRequest("A", ("G",))
    worker = SearchWorker(
        BFS,
        graph,
        request,
        comparison_mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm="",
    )
    completed = []
    failed = []
    worker.completed.connect(lambda result, runtime: completed.append(result))
    worker.failed.connect(failed.append)

    worker.run()

    assert not failed
    assert completed[0].success
    assert completed[0].path == ["A", "B", "G"]
    assert completed[0].comparison is None
    assert "comparison algorithm is required" in completed[0].comparison_error


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


def test_comparison_panel_presents_structured_explanation_sections():
    app = QApplication.instance() or QApplication([])
    graph = make_graph(
        ("A", "B", "C", "D", "G"),
        (
            ("A", "B", 1.0, 1.0, "local", 0.75, 0.0, "Đường Một"),
            ("B", "G", 1.0, 1.0, "local", 0.75, 0.0, "Đường Hai"),
            ("A", "C", 2.0, 2.0, "local", 1.0, 0.0, "Đường Ba"),
            ("C", "D", 2.0, 2.0, "local", 1.0, 0.0, "Đường Bốn"),
            ("D", "G", 2.0, 2.0, "local", 1.0, 0.0, "Đường Năm"),
        ),
    )
    selected = calculate_route_metrics(graph, ["A", "B", "G"])
    alternative = calculate_route_metrics(graph, ["A", "C", "D", "G"])
    comparison = compare_routes(selected, alternative, ASTAR, graph=graph)
    panel = RouteComparisonPanel([ASTAR, UCS])

    panel.set_comparison(comparison)

    assert panel.recommendation_title_label.text() == "Đề xuất: Selected · A* Search"
    assert "Total cost thấp hơn" in panel.recommendation_detail_label.text()
    assert "Alternative được tính lại" in panel.method_label.text()
    assert panel.congestion_toggle.text() == "Ùn tắc nặng (5 đoạn) · Xem chi tiết"
    assert panel.congestion_details.isHidden()
    assert "Đường Một · mức 0.75" in panel.selected_congestion_label.text()
    assert "A → B" in panel.selected_congestion_label.text()
    assert "Đường Ba · mức 1.00" in panel.alternative_congestion_label.text()

    panel.congestion_toggle.setChecked(True)

    assert not panel.congestion_details.isHidden()
    assert panel.congestion_toggle.text() == "Ùn tắc nặng (5 đoạn) · Thu gọn"
    assert "không tự khẳng định" in panel.optimality_label.text()
    assert panel.explanation_label.isHidden()
    assert "Gợi ý theo total cost" in panel.explanation_label.text()
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

    different_index = panel.mode_combo.findData(
        ComparisonMode.DIFFERENT_ALGORITHMS.value
    )
    panel.mode_combo.setCurrentIndex(different_index)

    assert requests == [(ComparisonMode.DIFFERENT_ALGORITHMS.value, UCS)]
    panel.deleteLater()
    app.processEvents()
