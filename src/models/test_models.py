import json
from pathlib import Path

import pytest

from src.models.graph_factory import build_graph
from src.models.models import Edge, Graph, Node, SearchResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DISTRICT5_DATASET = PROJECT_ROOT / "data" / "district5_subgraph_50nodes.json"


def test_graph_components_and_cost_contract():
    graph = Graph()
    node1 = Node(
        "N1",
        "Phu_Dong_Roundabout",
        lat=10.7712,
        lon=106.6924,
        node_type="intersection",
    )
    node2 = Node(
        "N2",
        "Dan_Chu_Roundabout",
        lat=10.7798,
        lon=106.6790,
        node_type="landmark",
    )
    graph.add_node(node1)
    graph.add_node(node2)

    assert graph.get_node("N1") is node1
    assert node1.lat == 10.7712
    assert node1.lon == 106.6924
    assert node1.node_type == "intersection"
    assert node2.node_type == "landmark"

    edge = Edge(
        "N1",
        "N2",
        distance=1.5,
        travel_time=5.0,
        road_type="primary",
        is_one_way=False,
        congestion=0.4,
        risk=0.2,
        note="Test road",
    )
    graph.add_edge(edge)

    assert graph.get_edge("N1", "N2") is edge
    reverse_edge = graph.get_edge("N2", "N1")
    assert reverse_edge is not None
    assert reverse_edge.from_node == "N2"
    assert reverse_edge.to_node == "N1"
    assert reverse_edge.note == "Test road"

    # Hand-built edges without normalized values retain the raw-cost fallback.
    assert edge.calculate_cost() == pytest.approx(6.5)

    edge.norm_distance = 0.5
    edge.norm_travel_time = 0.25
    weighted_cost = edge.calculate_cost(alpha=1.0, beta=1.5, gamma=2.0, delta=3.0)
    assert weighted_cost == pytest.approx(2.275)

    result = SearchResult(
        path=["N1", "N2"],
        steps=[{"type": "discover", "node": "N2"}],
        total_cost=weighted_cost,
        success=True,
        visited_order=["N1", "N2"],
    )
    assert result.success
    assert result.to_dict()["path"] == ["N1", "N2"]
    assert result.to_dict()["steps"][0]["type"] == "discover"
    assert result.total_cost == pytest.approx(2.275)


def test_build_graph_from_current_district5_dataset():
    assert DISTRICT5_DATASET.is_file()
    graph = build_graph(str(DISTRICT5_DATASET))

    edges = [
        edge
        for outgoing_edges in graph.adjacency_list.values()
        for edge in outgoing_edges
    ]
    assert len(graph.nodes) == 50
    assert len(edges) == 173

    node = graph.nodes["13420539060"]
    assert node.name == "Giao Lê Hồng Phong × Đường Nguyễn Trãi"
    assert node.lat == pytest.approx(10.7571834)
    assert node.lon == pytest.approx(106.6781278)
    assert node.node_type == "intersection"

    assert graph.max_distance > 0.0
    assert graph.max_time > 0.0
    assert all(0.0 <= edge.norm_distance <= 1.0 for edge in edges)
    assert all(0.0 <= edge.norm_travel_time <= 1.0 for edge in edges)
    assert all(edge.weight == pytest.approx(edge.calculate_cost()) for edge in edges)


def test_build_graph_accepts_legacy_coordinate_and_edge_keys(tmp_path):
    dataset = {
        "nodes": {
            "N1": {
                "id": "N1",
                "name": "Legacy landmark",
                "x": 10.77,
                "y": 106.68,
                "type": "landmark",
            },
            "N2": {"id": "N2", "name": "Node 2", "x": 10.78, "y": 106.69},
            "N3": {"id": "N3", "name": "Node 3", "x": 10.79, "y": 106.70},
        },
        "edges": [
            {
                "from": "N1",
                "to": "N2",
                "distance": 1.0,
                "travel_time": 2.0,
                "road_type": "local",
                "is_one_way": False,
            },
            {
                "u": "N2",
                "v": "N3",
                "distance": 0.5,
                "time": 1.0,
                "road_type": "local",
                "is_one_way": True,
            },
        ],
    }
    dataset_path = tmp_path / "legacy_graph.json"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    graph = build_graph(str(dataset_path))

    assert len(graph.nodes) == 3
    assert graph.nodes["N1"].lat == pytest.approx(10.77)
    assert graph.nodes["N1"].lon == pytest.approx(106.68)
    assert graph.nodes["N1"].node_type == "landmark"
    assert graph.get_edge("N1", "N2") is not None
    assert graph.get_edge("N2", "N1") is not None
    assert graph.get_edge("N2", "N3") is not None
    assert graph.get_edge("N3", "N2") is None
