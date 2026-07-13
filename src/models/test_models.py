# test_models.py
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(SRC_DIR)

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from models.models import Graph, Node, Edge, SearchResult
from models.graph_factory import build_graph


# AI write to test models.py
def test_ai_graph_components():
    print("=== STARTING MODELS.PY INTEGRATION TEST ===")

    # 1. Initialize Graph
    graph = Graph()

    # 2. Create and Add Nodes using the new lat/lon schema
    node1 = Node(
        "N1",
        "Phu_Dong_Roundabout",
        lat=10.7712,
        lon=106.6924,
        node_type="intersection",
    )
    node2 = Node("N2", "Dan_Chu_Roundabout", x=10.7798, y=106.6790)

    graph.add_node(node1)
    graph.add_node(node2)

    assert node1.lat == 10.7712
    assert node1.lon == 106.6924
    assert node1.x == node1.lat
    assert node1.y == node1.lon
    assert node1.type == "intersection"
    print(f"[SUCCESS] Nodes registered: {list(graph.nodes.values())}")

    # 3. Create and Add a directed edge with traffic constraints
    edge = Edge(
        "N1",
        "N2",
        distance=1.5,
        travel_time=5.0,
        road_type="Main Street",
        is_oneway=False,
        congestion=4,
        risk=2,
        note="Test road",
    )

    graph.add_edge(edge)
    print(f"[SUCCESS] Directed edge created. Outgoing from N1: {graph.adjacency_list['N1']}")

    assert len(graph.adjacency_list["N1"]) == 1
    assert len(graph.adjacency_list["N2"]) == 0
    assert edge.direction == "two-way"
    assert edge.flooding == edge.risk == 2
    assert graph.get_edge("N1", "N2") is edge

    # 4. Test optional legacy auto-reverse behavior
    legacy_graph = Graph()
    legacy_graph.add_node(node1)
    legacy_graph.add_node(node2)
    legacy_graph.add_edge(edge, auto_reverse=True)
    assert len(legacy_graph.adjacency_list["N2"]) == 1
    print(f"[SUCCESS] Optional reverse edge created. Outgoing from N2: {legacy_graph.adjacency_list['N2']}")

    # 5. Test Cost Function Under Different Scenarios
    print("\n--- Testing Dynamic Cost Functions ---")

    shortest_cost = edge.calculate_cost(mode="shortest")
    print(f"-> Shortest Mode Cost (Distance): {shortest_cost} km (Expected: 1.5)")
    assert shortest_cost == 1.5

    optimal_cost = edge.calculate_cost(alpha=1.0, beta=1.5, gamma=2.0, delta=3.0, mode="optimal")
    # Calculation: (1.0 * 1.5) + (1.5 * 5.0) + (2.0 * 4) + (3.0 * 2) = 23.0
    print(f"-> Optimal Mode Cost (Weighted): {optimal_cost} (Expected: 23.0)")
    assert optimal_cost == 23.0

    # 6. Test SearchResult contract
    result = SearchResult(
        path=["N1", "N2"],
        steps=[{"type": "visit_node", "node": "N1"}],
        total_cost=23.0,
        visited_order=["N1", "N2"],
    )
    assert result.success is True
    assert result.path == ["N1", "N2"]
    assert result.steps[0]["type"] == "visit_node"
    assert result.total_cost == 23.0
    print(f"[SUCCESS] SearchResult contract works: {result}")

    print("\n=== ALL BASIC MODEL TESTS PASSED SUCCESSFULLY! ===")


def test_build_graph_from_mock_data():
    print("\n=== STARTING MOCK DATA FACTORY TEST ===")

    json_path = os.path.join(PROJECT_ROOT, "data", "mock_data.json")
    graph = build_graph(json_path)

    total_edges = sum(len(edges) for edges in graph.adjacency_list.values())
    assert len(graph.nodes) == 5
    assert total_edges == 9

    node = graph.nodes["N01"]
    assert node.name == "Bách Khoa (Cổng chính)"
    assert node.lat == 10.7741
    assert node.lon == 106.6782
    assert node.type == "landmark"
    assert node.x == node.lat
    assert node.y == node.lon

    edge = graph.get_edge("N03", "N05")
    assert edge is not None
    assert edge.is_oneway is True
    assert edge.direction == "one-way"
    assert edge.risk == 1
    assert edge.flooding == 1
    assert edge.travel_time == 7.0
    assert edge.note == "Đường 1 chiều về phía Dân Chủ"

    print(f"[SUCCESS] mock_data.json loaded: {len(graph.nodes)} nodes, {total_edges} directed edges")
    print("=== MOCK DATA FACTORY TEST PASSED SUCCESSFULLY! ===")


def test_build_graph_from_legacy_map_data():
    print("\n=== STARTING LEGACY MAP DATA FACTORY TEST ===")

    json_path = os.path.join(PROJECT_ROOT, "data", "map_data.json")
    graph = build_graph(json_path)

    total_edges = sum(len(edges) for edges in graph.adjacency_list.values())
    assert len(graph.nodes) == 5
    # map_data.json has 3 two-way edges and 2 one-way edges => 5 + 3 reverse edges = 8 total.
    assert total_edges == 8

    node = graph.nodes["N1"]
    assert node.lat == 10.7785
    assert node.lon == 106.6795
    assert node.type == "intersection"

    assert graph.get_edge("N1", "N4") is not None
    assert graph.get_edge("N4", "N1") is not None
    assert graph.get_edge("N4", "N2") is not None
    assert graph.get_edge("N2", "N4") is None

    print(f"[SUCCESS] map_data.json loaded: {len(graph.nodes)} nodes, {total_edges} directed edges")
    print("=== LEGACY MAP DATA FACTORY TEST PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    test_ai_graph_components()
    test_build_graph_from_mock_data()
    test_build_graph_from_legacy_map_data()
