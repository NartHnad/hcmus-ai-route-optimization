import inspect

import pytest

from src.algorithms.beam_search import beam_search
from src.models.models import Edge, Graph, Node
from src.utils.heuristics import geographic_heuristic


def _weighted_edge(source, target):
    edge = Edge(
        source,
        target,
        distance=1.0,
        travel_time=1.0,
        road_type="local",
        is_one_way=True,
    )
    edge.norm_distance = 0.4
    edge.norm_travel_time = 0.2
    edge.weight = edge.calculate_cost()
    return edge


def _build_heuristic_choice_graph():
    graph = Graph()
    graph.max_distance = 1.0

    # A and B have equal path costs from S, but B is geographically close to
    # G. With beam_width=1, the shared heuristic must retain B instead of A.
    for node_id, longitude in (
        ("S", 0.0),
        ("A", 1.0),
        ("B", 0.01),
        ("G", 0.02),
    ):
        graph.add_node(Node(node_id, node_id, lat=0.0, lon=longitude))

    graph.add_edge(_weighted_edge("S", "A"))
    graph.add_edge(_weighted_edge("S", "B"))
    graph.add_edge(_weighted_edge("B", "G"))
    return graph


def test_beam_search_uses_shared_geographic_heuristic_for_ranking():
    graph = _build_heuristic_choice_graph()

    result = beam_search(graph, "S", "G", beam_width=1)

    assert result.success
    assert result.path == ["S", "B", "G"]

    discovered_b = next(
        step for step in result.steps
        if step.step_type.value == "discover" and step.node_id == "B"
    )
    expected_h = geographic_heuristic(graph, "B", "G")
    assert discovered_b.metrics["h"] == pytest.approx(expected_h)
    assert discovered_b.metrics["f"] == pytest.approx(
        discovered_b.metrics["g"] + expected_h
    )


def test_beam_search_api_no_longer_exposes_routing_mode():
    parameters = inspect.signature(beam_search).parameters

    assert "mode" not in parameters
    assert parameters["beam_width"].default == 10
