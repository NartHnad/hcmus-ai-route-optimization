from src.algorithms.algorithms import (
    get_algorithms,
    run_route_request,
    run_multi_location_algorithm,
)
from src.constants import StepType
from src.models.models import Edge, Graph, Node, RouteRequest


def _add_costed_edge(graph, source, target):
    edge = Edge(
        source,
        target,
        distance=1.0,
        travel_time=2.0,
        road_type="local",
        is_one_way=True,
    )
    edge.norm_distance = 1.0
    edge.norm_travel_time = 1.0
    edge.weight = edge.calculate_cost()
    graph.add_edge(edge)


def build_multi_goal_graph():
    graph = Graph()
    for node_id in ("S", "G2", "G10"):
        graph.add_node(Node(node_id, node_id, 10.0, 106.0))
    for source, target in (
        ("S", "G2"),
        ("S", "G10"),
        ("G2", "G10"),
        ("G10", "G2"),
    ):
        _add_costed_edge(graph, source, target)
    return graph


def test_algorithm_registry_keeps_single_and_multi_modes_separate():
    assert "A* Search" in get_algorithms("single")
    # #NhatHuyChanged: registry includes every production multi-location optimizer.
    assert get_algorithms("multi") == [
        "Mock Multi-location Search",
        "Nearest Neighbor + 2-Opt",
        "Simulated Annealing (SA)",
    ]


def test_ordered_multi_location_uses_ui_order_and_merges_real_legs():
    result = run_multi_location_algorithm(
        "Mock Multi-location Search",
        build_multi_goal_graph(),
        "S",
        ["G10", "G2"],
        respect_goal_order=True,
    )

    assert result.success
    assert result.goal_visit_order == ["G10", "G2"]
    assert result.path == ["S", "G10", "G2"]
    assert sum(step.step_type == StepType.FINISH for step in result.steps) == 1
    assert result.total_distance is None
    assert result.estimated_time is None
    assert result.to_dict()["goal_visit_order"] == ["G10", "G2"]

    leg_steps = [step for step in result.steps if step.step_type != StepType.FINISH]
    assert {step.metrics["leg_index"] for step in leg_steps} == {1, 2}
    assert all(step.metrics["leg_count"] == 2 for step in leg_steps)


def test_mock_optimize_mode_returns_deterministic_natural_goal_order():
    result = run_multi_location_algorithm(
        "Mock Multi-location Search",
        build_multi_goal_graph(),
        "S",
        ["G10", "G2"],
        respect_goal_order=False,
    )

    assert result.success
    assert result.goal_visit_order == ["G2", "G10"]
    assert result.path == ["S", "G2", "G10"]


def test_failed_leg_does_not_publish_a_partial_route():
    graph = Graph()
    for node_id in ("S", "A", "B"):
        graph.add_node(Node(node_id, node_id, 10.0, 106.0))
    _add_costed_edge(graph, "S", "A")

    result = run_multi_location_algorithm(
        "Mock Multi-location Search",
        graph,
        "S",
        ["A", "B"],
        respect_goal_order=True,
    )

    assert not result.success
    assert result.path == []
    assert "A -> B" in result.message
    finish = result.steps[-1]
    assert finish.step_type == StepType.FINISH
    assert finish.metrics["leg_start"] == "A"
    assert finish.metrics["leg_goal"] == "B"


def test_route_request_is_immutable_and_dispatches_by_route_mode():
    single = RouteRequest("S", ("G2",), False)
    multi = RouteRequest("S", ("G10", "G2"), False)

    assert single.route_mode == "single"
    assert multi.route_mode == "multi"
    try:
        single.start_node = "other"
        assert False, "RouteRequest must be immutable"
    except Exception:
        pass

    single_result = run_route_request("A* Search", build_multi_goal_graph(), single)
    multi_result = run_route_request(
        "Mock Multi-location Search", build_multi_goal_graph(), multi
    )
    assert single_result.success
    assert multi_result.goal_visit_order == ["G2", "G10"]
