import pytest

from src.models.graph_updater import (
    EdgeUpdateError,
    serialize_visual_edges,
    update_edge_attributes,
)
from src.models.models import Edge, Graph, Node


def _two_way_graph():
    graph = Graph()
    graph.max_distance = 2.0
    graph.max_time = 10.0
    graph.add_node(Node("A", "A", 10.0, 106.0))
    graph.add_node(Node("B", "B", 10.1, 106.1))
    edge = Edge(
        "A", "B", 1.0, 2.0, "local", is_one_way=False, congestion=0.1, risk=0.2
    )
    edge.norm_distance = 0.5
    edge.norm_travel_time = 0.2
    edge.weight = edge.calculate_cost()
    graph.add_edge(edge)
    return graph


def test_update_changes_only_the_selected_direction_and_never_distance():
    graph = _two_way_graph()
    reverse_before = graph.get_edge("B", "A")
    original_reverse = (
        reverse_before.distance,
        reverse_before.travel_time,
        reverse_before.risk,
        reverse_before.congestion,
    )

    payload = update_edge_attributes(graph, "A", "B", 5.0, 0.4, 0.2)

    forward = graph.get_edge("A", "B")
    assert forward.distance == 1.0
    assert forward.travel_time == 5.0
    assert forward.norm_travel_time == 0.5
    assert forward.weight == pytest.approx(forward.calculate_cost())
    assert payload["distance"] == 1.0
    assert (
        reverse_before.distance,
        reverse_before.travel_time,
        reverse_before.risk,
        reverse_before.congestion,
    ) == original_reverse


@pytest.mark.parametrize(
    "travel_time,risk,congestion",
    [(0, 0.2, 0.2), (float("nan"), 0.2, 0.2), (2, -0.1, 0.2), (2, 0.2, 1.1)],
)
def test_invalid_updates_are_atomic(travel_time, risk, congestion):
    graph = _two_way_graph()
    edge = graph.get_edge("A", "B")
    before = (edge.travel_time, edge.risk, edge.congestion, edge.weight)

    with pytest.raises(EdgeUpdateError):
        update_edge_attributes(graph, "A", "B", travel_time, risk, congestion)

    assert (edge.travel_time, edge.risk, edge.congestion, edge.weight) == before


def test_visual_edge_payload_keeps_direction_specific_details():
    graph = _two_way_graph()
    update_edge_attributes(graph, "B", "A", 7.0, 0.7, 0.6)

    visual = serialize_visual_edges(graph)

    assert len(visual) == 1
    details = {
        (item["from"], item["to"]): item for item in visual[0]["direction_details"]
    }
    assert set(details) == {("A", "B"), ("B", "A")}
    assert details[("A", "B")]["travel_time"] == 2.0
    assert details[("B", "A")]["travel_time"] == 7.0
