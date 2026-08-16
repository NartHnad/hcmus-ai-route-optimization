# #NhatHuyChanged: regression coverage for Nearest Neighbor + directed 2-Opt.
import math

from src.algorithms.algorithms import run_multi_location_algorithm, run_route_request
from src.algorithms.nearest_neighbor_2opt import (
    ALGORITHM_NAME,
    nearest_neighbor_order,
    route_cost,
    two_opt,
)
from src.constants import StepType
from src.models.models import Edge, Graph, Node, RouteRequest


def _add_directed_edge(graph, source, target, cost):
    edge = Edge(
        source,
        target,
        distance=cost,
        travel_time=cost,
        road_type="local",
        is_one_way=True,
    )
    edge.norm_distance = float(cost) * 4.0
    edge.norm_travel_time = 0.0
    edge.weight = edge.calculate_cost()
    graph.add_edge(edge)


def _build_two_goal_graph():
    graph = Graph()
    for node_id in ("S", "A", "B"):
        graph.add_node(Node(node_id, node_id, 10.0, 106.0))
    _add_directed_edge(graph, "S", "A", 1.0)
    _add_directed_edge(graph, "S", "B", 2.0)
    _add_directed_edge(graph, "A", "B", 10.0)
    _add_directed_edge(graph, "B", "A", 1.0)
    return graph


def test_two_opt_improves_the_directed_nearest_neighbor_route():
    costs = {
        ("S", "A"): 1.0,
        ("S", "B"): 2.0,
        ("A", "B"): 10.0,
        ("B", "A"): 1.0,
    }
    initial = nearest_neighbor_order("S", ["A", "B"], costs)
    optimized, optimized_cost, improvements = two_opt(initial, costs)

    assert initial == ["S", "A", "B"]
    assert route_cost(initial, costs) == 11.0
    assert optimized == ["S", "B", "A"]
    assert optimized_cost == 3.0
    assert len(improvements) == 1


def test_algorithm_returns_real_road_path_and_goal_order():
    result = run_multi_location_algorithm(
        ALGORITHM_NAME,
        _build_two_goal_graph(),
        "S",
        ["A", "B"],
        respect_goal_order=False,
    )

    assert result.success
    assert result.path == ["S", "B", "A"]
    assert result.goal_visit_order == ["B", "A"]
    assert math.isclose(result.total_cost, 3.0)
    assert sum(step.step_type == StepType.FINISH for step in result.steps) == 1
    assert result.steps[-1].metrics["2opt_improvements"] == 1
    assert result.to_dict()["goal_visit_order"] == ["B", "A"]


def test_respect_goal_order_skips_optimization():
    result = run_multi_location_algorithm(
        ALGORITHM_NAME,
        _build_two_goal_graph(),
        "S",
        ["A", "B"],
        respect_goal_order=True,
    )

    assert result.success
    assert result.path == ["S", "A", "B"]
    assert result.goal_visit_order == ["A", "B"]
    assert math.isclose(result.total_cost, 11.0)
    assert result.steps[-1].metrics["2opt_improvements"] == 0


def test_unreachable_goal_fails_without_partial_route():
    graph = Graph()
    for node_id in ("S", "A", "B"):
        graph.add_node(Node(node_id, node_id, 10.0, 106.0))
    _add_directed_edge(graph, "S", "A", 1.0)

    result = run_multi_location_algorithm(ALGORITHM_NAME, graph, "S", ["A", "B"])

    assert not result.success
    assert result.path == []
    assert len(result.steps) == 1
    assert result.steps[0].step_type == StepType.FINISH
    assert "could not reach" in result.message


def test_invalid_goal_requests_are_rejected():
    graph = _build_two_goal_graph()
    cases = [
        (["A", "A"], "unique"),
        (["S", "A"], "cannot also be a goal"),
        (["A", "MISSING"], "was not found"),
    ]

    for goals, message_fragment in cases:
        result = run_multi_location_algorithm(ALGORITHM_NAME, graph, "S", goals)
        assert not result.success
        assert result.path == []
        assert result.steps[-1].step_type == StepType.FINISH
        assert message_fragment in result.message


def test_route_request_dispatches_to_nearest_neighbor_2opt():
    request = RouteRequest("S", ("A", "B"), False)
    result = run_route_request(ALGORITHM_NAME, _build_two_goal_graph(), request)

    assert result.success
    assert result.goal_visit_order == ["B", "A"]
