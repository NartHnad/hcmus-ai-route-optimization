import random

from src.algorithms.algorithms import get_algorithms, run_algorithm
from src.gui.graph_widget import GraphWidget
from src.models.models import Edge, Graph, Node, SearchResult, SearchStep, StepType


def build_small_graph():
    graph = Graph()
    graph.add_node(Node("A", "Start", 10.0, 106.0))
    graph.add_node(Node("B", "Middle", 10.001, 106.001))
    graph.add_node(Node("C", "Goal", 10.002, 106.002))
    graph.add_edge(Edge("A", "B", 1.0, 2.0, "local", is_one_way=True))
    graph.add_edge(Edge("B", "C", 1.0, 2.0, "local", is_one_way=True))
    return graph


def test_public_algorithms_use_the_visualization_contract():
    random.seed(7)
    graph = build_small_graph()
    algorithms = get_algorithms()

    assert "Mock 3 Search" not in algorithms
    assert "Uniform Cost Search (UCS)" in algorithms

    for algorithm in algorithms:
        result = run_algorithm(algorithm, graph, "A", "C")
        assert isinstance(result, SearchResult)
        assert result.success
        assert result.path[0] == "A"
        assert result.path[-1] == "C"

        serialized_steps = result.to_dict()["steps"]
        assert serialized_steps[-1]["type"] == "finish"
        assert any(step["type"] in {"discover", "update"} for step in serialized_steps)
        assert all(
            step["type"] in {"expand", "discover", "update", "finish"}
            for step in serialized_steps
        )


def test_search_step_and_result_include_ui_metrics():
    step = SearchStep(
        StepType.DISCOVER,
        node_id="B",
        edge_from="A",
        edge_to="B",
        metrics={"g": 1.0, "h": 2.0, "f": 3.0},
        frontier=["B"],
        explored=["A"],
        visited_order=["A"],
    )
    result = SearchResult(
        path=["A", "B"],
        steps=[step],
        total_cost=1.0,
        success=True,
        runtime_ms=2.5,
        total_distance=1.0,
        estimated_time=2.0,
    )

    serialized = result.to_dict()
    assert serialized["runtime_ms"] == 2.5
    assert serialized["total_distance"] == 1.0
    assert serialized["estimated_time"] == 2.0
    assert serialized["steps"][0]["frontier"] == ["B"]
    assert serialized["steps"][0]["metrics"]["f"] == 3.0


def build_branching_graph():
    graph = Graph()
    for node_id in ("A", "B", "C", "G"):
        # Equal coordinates make the A* heuristic zero, isolating its actual
        # queue/cost behavior in this regression test.
        graph.add_node(Node(node_id, node_id, 10.0, 106.0))
    for source, target, distance in (
        ("A", "B", 1.0),
        ("A", "C", 1.0),
        ("B", "G", 8.0),
        ("C", "G", 1.0),
    ):
        graph.add_edge(
            Edge(
                source,
                target,
                distance,
                distance,
                "local",
                is_one_way=True,
                congestion=0,
                risk=0,
            )
        )
    return graph


def test_delta_steps_preserve_algorithm_selection_and_costs():
    graph = build_branching_graph()

    bfs_result = run_algorithm("Breadth-First Search (BFS)", graph, "A", "G")
    dfs_result = run_algorithm("Depth-First Search (DFS)", graph, "A", "G")
    ucs_result = run_algorithm("Uniform Cost Search (UCS)", graph, "A", "G")
    astar_result = run_algorithm("A* Search", graph, "A", "G")

    assert bfs_result.path == ["A", "B", "G"]
    assert bfs_result.total_cost == 18.0
    assert dfs_result.path == ["A", "C", "G"]
    assert dfs_result.total_cost == 4.0
    assert ucs_result.path == ["A", "C", "G"]
    assert ucs_result.total_cost == 4.0
    assert astar_result.path == ["A", "C", "G"]
    assert astar_result.total_cost == 4.0


def test_core_search_events_do_not_retain_full_state_snapshots():
    graph = build_branching_graph()
    for algorithm in (
        "Breadth-First Search (BFS)",
        "Depth-First Search (DFS)",
        "Uniform Cost Search (UCS)",
        "A* Search",
    ):
        result = run_algorithm(algorithm, graph, "A", "G")
        for step in result.steps:
            assert step.frontier is None
            assert step.explored is None
            assert step.visited_order is None


def test_graph_view_payload_deduplicates_visual_edges_without_losing_direction():
    graph = Graph()
    graph.add_node(Node("A", "Alpha", 10.0, 106.0))
    graph.add_node(Node("B", "Beta", 10.1, 106.1))
    graph.add_edge(Edge("A", "B", 2.0, 3.0, "local", is_one_way=False))

    payload = GraphWidget._serialize_graph(graph)

    assert len(payload["nodes"]) == 2
    assert len(payload["edges"]) == 1
    edge = payload["edges"][0]
    assert {tuple(direction) for direction in edge["directions"]} == {
        ("A", "B"),
        ("B", "A"),
    }
    assert edge["cost"] == 5.0
    assert len(edge["direction_details"]) == 2
