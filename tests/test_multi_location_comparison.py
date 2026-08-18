import os
import random

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import src.algorithms.route_comparison as route_comparison_module
import src.gui.main_window as main_window_module
from src.algorithms.algorithms import get_algorithms, run_route_request
from src.algorithms.route_comparison import (
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
    RouteRequest,
    SearchResult,
)


NN_2OPT = "Nearest Neighbor + 2-Opt"
GA = "Genetic Algorithm (GA)"
SA = "Simulated Annealing (SA)"


def _complete_graph():
    graph = Graph()
    node_ids = ("S", "A", "B", "C")
    for index, node_id in enumerate(node_ids):
        graph.add_node(Node(node_id, node_id, 10.0 + index * 0.001, 106.0))
    for source_index, source in enumerate(node_ids):
        for target_index, target in enumerate(node_ids):
            if source == target:
                continue
            graph.add_edge(
                Edge(
                    source,
                    target,
                    distance=1.0 + abs(source_index - target_index) * 0.1,
                    travel_time=2.0 + target_index * 0.1,
                    road_type="local",
                    is_one_way=True,
                    congestion=0.1 * target_index,
                    risk=0.0,
                    note=f"{source}{target}",
                )
            )
    return graph


def _optimization_graph():
    """Directed graph with a deterministic cheaper B → C → A goal order."""
    graph = Graph()
    node_ids = ("S", "A", "B", "C")
    for node_id in node_ids:
        # Identical coordinates make A*'s heuristic zero for these test routes.
        graph.add_node(Node(node_id, node_id, 10.0, 106.0))

    weights = {
        ("S", "A"): 2.9,
        ("S", "B"): 1.0,
        ("S", "C"): 2.0,
        ("A", "B"): 5.0,
        ("B", "C"): 1.0,
        ("C", "A"): 1.0,
    }
    for source in node_ids:
        for target in node_ids:
            if source == target:
                continue
            cost = weights.get((source, target), 10.0)
            graph.add_edge(
                Edge(
                    source,
                    target,
                    distance=cost / 2.0,
                    travel_time=cost / 2.0,
                    road_type="local",
                    is_one_way=True,
                    congestion=0.0,
                    risk=0.0,
                    note=f"{source}{target}",
                )
            )
    return graph


def _result(order, *, return_to_start=False):
    path = ["S", *order]
    if return_to_start:
        path.append("S")
    return SearchResult(
        path=path,
        success=True,
        total_cost=123.0,
        visited_order=list(path),
        goal_visit_order=list(order),
    )


def _graph_signature(graph):
    node_state = tuple(
        (
            node_id,
            id(node),
            node.name,
            node.lat,
            node.lon,
            node.node_type,
        )
        for node_id, node in sorted(graph.nodes.items())
    )
    edge_state = tuple(
        (
            source,
            id(edge),
            edge.from_node,
            edge.to_node,
            edge.distance,
            edge.travel_time,
            edge.congestion,
            edge.risk,
            edge.norm_distance,
            edge.norm_travel_time,
            edge.weight,
        )
        for source in sorted(graph.adjacency_list)
        for edge in graph.adjacency_list[source]
    )
    incoming_state = tuple(
        (target, tuple(id(edge) for edge in graph.incoming_adjacency_list[target]))
        for target in sorted(graph.incoming_adjacency_list)
    )
    return node_state, edge_state, incoming_state


def test_ml_comp_01_nn_2opt_and_ga_receive_the_exact_same_request(monkeypatch):
    graph = _complete_graph()
    request = RouteRequest("S", ("A", "B", "C"))
    calls = []

    def tracking_runner(name, supplied_graph, supplied_request):
        calls.append((name, supplied_graph, supplied_request))
        order = ["C", "A", "B"] if name == NN_2OPT else ["A", "C", "B"]
        return _result(order)

    monkeypatch.setattr(main_window_module, "run_route_request", tracking_runner)
    monkeypatch.setattr(route_comparison_module, "run_route_request", tracking_runner)
    worker = SearchWorker(
        NN_2OPT,
        graph,
        request,
        comparison_mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=GA,
    )
    completed = []
    worker.completed.connect(lambda result, _runtime: completed.append(result))

    worker.run()

    assert [call[0] for call in calls] == [NN_2OPT, GA]
    assert all(call[1] is graph for call in calls)
    assert all(call[2] is request for call in calls)
    assert completed[0].comparison.route_mode == "multi"


def test_ml_comp_02_ga_and_sa_preserve_all_route_request_fields(monkeypatch):
    graph = _complete_graph()
    request = RouteRequest(
        "S",
        ("A", "B", "C"),
        respect_goal_order=True,
        return_to_start=True,
    )
    calls = []

    def tracking_runner(name, supplied_graph, supplied_request):
        calls.append((name, supplied_graph, supplied_request))
        return _result(["A", "B", "C"], return_to_start=True)

    monkeypatch.setattr(route_comparison_module, "run_route_request", tracking_runner)
    comparison = build_route_comparison(
        graph,
        _result(["A", "B", "C"], return_to_start=True),
        GA,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=SA,
        route_request=request,
    )

    assert calls == [(SA, graph, request)]
    assert comparison.original_goal_order == ["A", "B", "C"]
    assert comparison.respect_goal_order is True
    assert comparison.return_to_start is True


def test_ml_comp_03_different_goal_orders_are_kept_and_displayed(monkeypatch):
    app = QApplication.instance() or QApplication([])
    graph = _complete_graph()
    request = RouteRequest("S", ("A", "B", "C"))
    monkeypatch.setattr(
        route_comparison_module,
        "run_route_request",
        lambda *_args: _result(["A", "C", "B"]),
    )
    comparison = build_route_comparison(
        graph,
        _result(["C", "B", "A"]),
        GA,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=SA,
        route_request=request,
    )
    panel = RouteComparisonPanel(get_algorithms("multi"), route_mode="multi")

    panel.set_comparison(comparison)

    assert comparison.selected.goal_visit_order == ["C", "B", "A"]
    assert comparison.alternative.goal_visit_order == ["A", "C", "B"]
    assert "S → C → B → A" in panel.selected_order_label.text()
    assert "S → A → C → B" in panel.alternative_order_label.text()
    assert not panel.selected_order_label.isHidden()
    assert "Full graph path Route A" in panel.selected_route_label.text()
    panel.deleteLater()
    app.processEvents()


def test_ml_comp_04_comparison_does_not_mutate_original_request(monkeypatch):
    graph = _complete_graph()
    request = RouteRequest("S", ("A", "B", "C"), False, True)
    before = (
        request.start_node,
        request.delivery_nodes,
        request.respect_goal_order,
        request.return_to_start,
    )
    monkeypatch.setattr(
        route_comparison_module,
        "run_route_request",
        lambda *_args: _result(["B", "A", "C"], return_to_start=True),
    )

    build_route_comparison(
        graph,
        _result(["C", "B", "A"], return_to_start=True),
        NN_2OPT,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=GA,
        route_request=request,
    )

    assert before == (
        request.start_node,
        request.delivery_nodes,
        request.respect_goal_order,
        request.return_to_start,
    )


def test_ml_comp_05_comparison_does_not_mutate_graph_or_edges(monkeypatch):
    graph = _complete_graph()
    request = RouteRequest("S", ("A", "B", "C"))
    before = _graph_signature(graph)
    monkeypatch.setattr(
        route_comparison_module,
        "run_route_request",
        lambda *_args: _result(["B", "A", "C"]),
    )

    build_route_comparison(
        graph,
        _result(["C", "B", "A"]),
        NN_2OPT,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=GA,
        route_request=request,
    )

    assert _graph_signature(graph) == before


def test_ml_comp_06_primary_algorithm_result_remains_unchanged(monkeypatch):
    graph = _complete_graph()
    request = RouteRequest("S", ("A", "B", "C"))
    primary = _result(["C", "A", "B"])
    before = (
        list(primary.path),
        list(primary.goal_visit_order),
        primary.total_cost,
        primary.success,
    )
    monkeypatch.setattr(
        route_comparison_module,
        "run_route_request",
        lambda *_args: _result(["A", "B", "C"]),
    )

    build_route_comparison(
        graph,
        primary,
        NN_2OPT,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=GA,
        route_request=request,
    )

    assert before == (
        primary.path,
        primary.goal_visit_order,
        primary.total_cost,
        primary.success,
    )


def test_ml_comp_07_selector_contains_only_multi_location_algorithms():
    app = QApplication.instance() or QApplication([])
    all_algorithms = get_algorithms("single") + get_algorithms("multi")
    panel = RouteComparisonPanel(all_algorithms, route_mode="multi")

    panel.configure(NN_2OPT, all_algorithms, route_mode="multi")

    choices = {
        panel.algorithm_combo.itemText(index)
        for index in range(panel.algorithm_combo.count())
    }
    assert choices == set(get_algorithms("multi")) - {NN_2OPT}
    incompatible = set(get_algorithms("single")) - set(get_algorithms("multi"))
    assert choices.isdisjoint(incompatible)
    panel.deleteLater()
    app.processEvents()


def test_ml_comp_08_explanation_includes_visiting_order_difference(monkeypatch):
    graph = _complete_graph()
    request = RouteRequest("S", ("A", "B", "C"))
    monkeypatch.setattr(
        route_comparison_module,
        "run_route_request",
        lambda *_args: _result(["A", "C", "B"]),
    )

    comparison = build_route_comparison(
        graph,
        _result(["C", "B", "A"]),
        GA,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=SA,
        route_request=request,
    )

    assert "C → B → A" in comparison.explanation.text
    assert "A → C → B" in comparison.explanation.text
    assert "lần chạy hiện tại" in comparison.explanation.text


def test_ml_comp_09_heuristic_explanations_never_claim_global_optimality():
    for algorithm in (NN_2OPT, GA, SA):
        statement = optimality_statement(algorithm)
        assert "không bảo đảm nghiệm tối ưu toàn cục" in statement
        assert "bảo đảm nghiệm tối ưu toàn cục" not in statement.replace(
            "không bảo đảm nghiệm tối ưu toàn cục", ""
        )


def test_ml_comp_10_return_to_start_is_preserved_for_both_routes(monkeypatch):
    app = QApplication.instance() or QApplication([])
    graph = _complete_graph()
    request = RouteRequest("S", ("A", "B", "C"), False, True)
    monkeypatch.setattr(
        route_comparison_module,
        "run_route_request",
        lambda *_args: _result(["B", "A", "C"], return_to_start=True),
    )
    comparison = build_route_comparison(
        graph,
        _result(["C", "B", "A"], return_to_start=True),
        GA,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=SA,
        route_request=request,
    )
    panel = RouteComparisonPanel(get_algorithms("multi"), route_mode="multi")

    panel.set_comparison(comparison)

    assert comparison.selected.return_to_start is True
    assert comparison.alternative.return_to_start is True
    assert comparison.selected.path[-1] == "S"
    assert comparison.alternative.path[-1] == "S"
    assert panel.selected_order_label.text().endswith("S")
    assert panel.alternative_order_label.text().endswith("S")
    panel.deleteLater()
    app.processEvents()


def test_ml_comp_11_original_order_vs_optimized_order(monkeypatch):
    graph = _complete_graph()
    request = RouteRequest("S", ("A", "B", "C"), False, False)
    supplied_requests = []

    def original_order_runner(name, supplied_graph, supplied_request):
        supplied_requests.append(supplied_request)
        assert name == NN_2OPT
        assert supplied_graph is graph
        return _result(list(supplied_request.delivery_nodes))

    monkeypatch.setattr(
        route_comparison_module,
        "run_route_request",
        original_order_runner,
    )
    comparison = build_route_comparison(
        graph,
        _result(["C", "A", "B"]),
        NN_2OPT,
        mode=ComparisonMode.ORIGINAL_VS_OPTIMIZED,
        route_request=request,
    )

    assert supplied_requests[0] is not request
    assert supplied_requests[0].delivery_nodes == request.delivery_nodes
    assert supplied_requests[0].respect_goal_order is True
    assert supplied_requests[0].return_to_start == request.return_to_start
    assert request.respect_goal_order is False
    assert comparison.selected.goal_visit_order == ["A", "B", "C"]
    assert comparison.alternative.goal_visit_order == ["C", "A", "B"]
    assert "Thứ tự ghé ban đầu là A → B → C" in comparison.explanation.text
    assert "C → A → B" in comparison.explanation.text


@pytest.mark.parametrize("comparison_algorithm", [GA, SA])
def test_ml_comp_12_secondary_stochastic_algorithm_does_not_leak_rng_state(
    comparison_algorithm,
):
    graph = _complete_graph()
    request = RouteRequest("S", ("A", "B", "C"))
    random.seed(20260818)
    state_before = random.getstate()

    build_route_comparison(
        graph,
        _result(["A", "B", "C"]),
        NN_2OPT,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=comparison_algorithm,
        route_request=request,
    )

    assert random.getstate() == state_before


@pytest.mark.parametrize("algorithm", [NN_2OPT, GA, SA])
def test_ml_comp_13_real_algorithms_preserve_supplied_fixed_order(algorithm):
    graph = _complete_graph()
    request = RouteRequest(
        "S",
        ("A", "B", "C"),
        respect_goal_order=True,
        return_to_start=False,
    )

    result = run_route_request(algorithm, graph, request)

    assert result.success, result.message
    assert result.goal_visit_order == ["A", "B", "C"]
    assert result.path[0] == "S"
    assert result.path[-1] == "C"
    if algorithm == GA:
        assert "optimization was skipped" in result.message
    if algorithm == SA:
        assert "no SA optimization performed" in result.message


def test_ml_comp_14_real_original_vs_optimized_routes_and_metrics():
    graph = _optimization_graph()
    request = RouteRequest("S", ("A", "B", "C"))
    primary = run_route_request(NN_2OPT, graph, request)
    primary_before = (
        list(primary.path),
        list(primary.goal_visit_order),
        primary.total_cost,
        primary.success,
        list(primary.visited_order),
        list(primary.steps),
    )

    comparison = build_route_comparison(
        graph,
        primary,
        NN_2OPT,
        mode=ComparisonMode.ORIGINAL_VS_OPTIMIZED,
        route_request=request,
    )

    assert comparison.selected.goal_visit_order == ["A", "B", "C"]
    assert comparison.alternative.goal_visit_order == ["B", "C", "A"]
    assert comparison.selected.path == ["S", "A", "B", "C"]
    assert comparison.alternative.path == ["S", "B", "C", "A"]
    assert comparison.selected.total_cost == pytest.approx(8.9)
    assert comparison.alternative.total_cost == pytest.approx(3.0)
    assert comparison.selected.total_cost == pytest.approx(
        sum(segment.total_cost for segment in comparison.selected.segments)
    )
    assert comparison.alternative.total_cost == pytest.approx(
        sum(segment.total_cost for segment in comparison.alternative.segments)
    )
    assert primary_before == (
        primary.path,
        primary.goal_visit_order,
        primary.total_cost,
        primary.success,
        primary.visited_order,
        primary.steps,
    )


@pytest.mark.parametrize(
    ("selected_path", "alternative_path", "expected", "unexpected"),
    [
        (
            ["S", "A", "S"],
            ["S", "B", "S"],
            "Cả hai tuyến đều quay về điểm bắt đầu S.",
            "không hoàn tất yêu cầu",
        ),
        (
            ["S", "A", "S"],
            ["S", "B"],
            "Route A quay về điểm bắt đầu S, nhưng Route B không hoàn tất",
            "Cả hai tuyến đều quay về",
        ),
        (
            ["S", "A"],
            ["S", "B"],
            "Hai kết quả hiện tại không hoàn tất yêu cầu quay về điểm bắt đầu.",
            "Cả hai tuyến đều quay về",
        ),
    ],
)
def test_ml_comp_15_return_explanation_checks_actual_endpoints(
    selected_path,
    alternative_path,
    expected,
    unexpected,
):
    graph = _complete_graph()
    selected = calculate_route_metrics(graph, selected_path)
    alternative = calculate_route_metrics(graph, alternative_path)
    selected.start_node = "S"
    alternative.start_node = "S"

    comparison = compare_routes(
        selected,
        alternative,
        GA,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=SA,
        graph=graph,
        route_mode="multi",
        original_goal_order=("A", "B", "C"),
        return_to_start=True,
    )

    assert expected in comparison.explanation.text
    assert unexpected not in comparison.explanation.text


def test_ml_comp_16_single_multi_single_panel_transition():
    app = QApplication.instance() or QApplication([])
    all_algorithms = get_algorithms("single") + get_algorithms("multi")
    bfs = "Breadth-First Search (BFS)"
    panel = RouteComparisonPanel(all_algorithms, route_mode="single")

    panel.configure(bfs, all_algorithms, route_mode="single")
    assert {
        panel.mode_combo.itemData(index)
        for index in range(panel.mode_combo.count())
    } == {
        ComparisonMode.SAME_ALGORITHM_ALTERNATIVE.value,
        ComparisonMode.DIFFERENT_ALGORITHMS.value,
    }

    panel.configure(NN_2OPT, all_algorithms, route_mode="multi")
    assert {
        panel.mode_combo.itemData(index)
        for index in range(panel.mode_combo.count())
    } == {
        ComparisonMode.DIFFERENT_ALGORITHMS.value,
        ComparisonMode.ORIGINAL_VS_OPTIMIZED.value,
    }
    assert {
        panel.algorithm_combo.itemText(index)
        for index in range(panel.algorithm_combo.count())
    } == set(get_algorithms("multi")) - {NN_2OPT}

    panel.configure(bfs, all_algorithms, route_mode="single")
    assert {
        panel.mode_combo.itemData(index)
        for index in range(panel.mode_combo.count())
    } == {
        ComparisonMode.SAME_ALGORITHM_ALTERNATIVE.value,
        ComparisonMode.DIFFERENT_ALGORITHMS.value,
    }
    panel.deleteLater()
    app.processEvents()


def test_ml_comp_17_fixed_order_request_hides_optimization_comparison():
    app = QApplication.instance() or QApplication([])
    panel = RouteComparisonPanel(get_algorithms("multi"), route_mode="multi")

    panel.configure(
        NN_2OPT,
        get_algorithms("multi"),
        route_mode="multi",
        respect_goal_order=True,
    )

    modes = {
        panel.mode_combo.itemData(index)
        for index in range(panel.mode_combo.count())
    }
    assert ComparisonMode.ORIGINAL_VS_OPTIMIZED.value not in modes
    assert modes == {ComparisonMode.DIFFERENT_ALGORITHMS.value}
    assert "preserved" in panel.mode_combo.toolTip()
    panel.deleteLater()
    app.processEvents()


def test_ml_comp_18_explicit_route_mode_wins_over_mixed_algorithm_list():
    app = QApplication.instance() or QApplication([])
    bfs = "Breadth-First Search (BFS)"
    mixed = [NN_2OPT, bfs, GA]
    panel = RouteComparisonPanel(mixed, route_mode="single")

    panel.configure(
        NN_2OPT,
        mixed,
        route_mode="multi",
        respect_goal_order=False,
    )
    assert panel._route_mode == "multi"
    assert panel.mode_combo.findData(
        ComparisonMode.ORIGINAL_VS_OPTIMIZED.value
    ) >= 0
    assert {
        panel.algorithm_combo.itemText(index)
        for index in range(panel.algorithm_combo.count())
    } == {GA}

    panel.configure(bfs, mixed, route_mode="single")
    assert panel._route_mode == "single"
    assert panel.mode_combo.findData(
        ComparisonMode.SAME_ALGORITHM_ALTERNATIVE.value
    ) >= 0
    assert panel.mode_combo.findData(
        ComparisonMode.ORIGINAL_VS_OPTIMIZED.value
    ) == -1
    panel.deleteLater()
    app.processEvents()


def test_processing_time_explanation_is_scoped_to_current_execution():
    graph = _complete_graph()
    selected = calculate_route_metrics(graph, ["S", "A"])
    alternative = calculate_route_metrics(graph, ["S", "B"])
    selected.processing_time_ms = 5.0
    alternative.processing_time_ms = 10.0

    comparison = compare_routes(
        selected,
        alternative,
        GA,
        mode=ComparisonMode.DIFFERENT_ALGORITHMS,
        comparison_algorithm=SA,
        graph=graph,
    )

    assert (
        "Trong lần chạy hiện tại, Route A có thời gian xử lý thấp hơn "
        "Route B 5.00 ms."
    ) in comparison.explanation.text
    assert "Thời gian xử lý: Route A tốt hơn" not in comparison.explanation.text


def test_original_vs_optimized_rejects_an_already_fixed_order_request():
    graph = _complete_graph()
    request = RouteRequest(
        "S",
        ("A", "B", "C"),
        respect_goal_order=True,
    )
    primary = run_route_request(NN_2OPT, graph, request)

    with pytest.raises(ValueError, match="preserves the supplied visiting order"):
        build_route_comparison(
            graph,
            primary,
            NN_2OPT,
            mode=ComparisonMode.ORIGINAL_VS_OPTIMIZED,
            route_request=request,
        )
