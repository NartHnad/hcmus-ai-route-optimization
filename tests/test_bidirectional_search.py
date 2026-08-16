# #NhatHuyChanged: regression coverage for weighted, directed Bidirectional Search.
import heapq
import math
import random
import unittest

from src.algorithms.algorithms import get_algorithms, run_algorithm
from src.algorithms.bidirectional_search import ALGORITHM_NAME, bidirectional_search
from src.constants import DEFAULT_ALPHA, StepType
from src.models.models import Edge, Graph, Node, SearchResult


def _graph(node_ids):
    graph = Graph()
    for index, node_id in enumerate(node_ids):
        graph.add_node(Node(node_id, node_id, 10.0 + index / 1000, 106.0))
    return graph


def _add_directed_edge(graph, source, target, cost):
    edge = Edge(
        source,
        target,
        distance=cost,
        travel_time=0.0,
        road_type="local",
        is_one_way=True,
    )
    # Isolate the composite cost to alpha * normalized distance.
    edge.norm_distance = cost / DEFAULT_ALPHA
    edge.norm_travel_time = 0.0
    edge.weight = edge.calculate_cost()
    graph.add_edge(edge)


def _reference_dijkstra(graph, start, goal):
    distances = {start: 0.0}
    frontier = [(0.0, start)]
    settled = set()
    while frontier:
        current_cost, current = heapq.heappop(frontier)
        if current in settled:
            continue
        settled.add(current)
        if current == goal:
            return current_cost
        for edge in graph.get_neighbors(current):
            candidate = current_cost + edge.calculate_cost()
            if candidate < distances.get(edge.to_node, math.inf):
                distances[edge.to_node] = candidate
                heapq.heappush(frontier, (candidate, edge.to_node))
    return math.inf


class BidirectionalSearchTests(unittest.TestCase):
    def test_registry_keeps_bidirectional_and_multi_location_algorithms_separate(self):
        self.assertIn(ALGORITHM_NAME, get_algorithms("single"))
        self.assertNotIn(ALGORITHM_NAME, get_algorithms("multi"))
        self.assertIn("Nearest Neighbor + 2-Opt", get_algorithms("multi"))

    def test_finds_optimal_weighted_path_and_emits_both_directions(self):
        graph = _graph(("S", "A", "B", "C", "G"))
        for source, target, cost in (
            ("S", "A", 1.0),
            ("A", "G", 10.0),
            ("S", "B", 2.0),
            ("B", "C", 2.0),
            ("C", "G", 2.0),
        ):
            _add_directed_edge(graph, source, target, cost)

        result = run_algorithm(ALGORITHM_NAME, graph, "S", "G")

        self.assertIsInstance(result, SearchResult)
        self.assertTrue(result.success)
        self.assertEqual(["S", "B", "C", "G"], result.path)
        self.assertTrue(math.isclose(6.0, result.total_cost))
        directions = {
            step.metrics.get("search_direction")
            for step in result.steps
            if step.step_type != StepType.FINISH
        }
        self.assertEqual({"forward", "backward"}, directions)
        self.assertEqual("C", result.steps[-1].metrics["meeting_node"])
        self.assertTrue(result.steps[-1].metrics["optimal"])

    def test_reverse_search_respects_one_way_edges(self):
        graph = _graph(("A", "B"))
        _add_directed_edge(graph, "A", "B", 1.0)

        reachable = bidirectional_search(graph, "A", "B")
        blocked = bidirectional_search(graph, "B", "A")

        self.assertTrue(reachable.success)
        self.assertEqual(["A", "B"], reachable.path)
        self.assertFalse(blocked.success)
        self.assertEqual([], blocked.path)

    def test_graph_indexes_both_directions_of_a_two_way_edge(self):
        graph = _graph(("A", "B"))
        edge = Edge("A", "B", 1.0, 1.0, "local", is_one_way=False)
        edge.norm_distance = 1.0
        edge.norm_travel_time = 1.0
        graph.add_edge(edge)

        incoming_a = {
            (item.from_node, item.to_node)
            for item in graph.get_incoming_neighbors("A")
        }
        incoming_b = {
            (item.from_node, item.to_node)
            for item in graph.get_incoming_neighbors("B")
        }
        self.assertEqual({("B", "A")}, incoming_a)
        self.assertEqual({("A", "B")}, incoming_b)

    def test_start_equals_goal_returns_zero_cost_route(self):
        graph = _graph(("S",))

        result = bidirectional_search(graph, "S", "S")

        self.assertTrue(result.success)
        self.assertEqual(["S"], result.path)
        self.assertEqual(0.0, result.total_cost)
        self.assertEqual(StepType.FINISH, result.steps[-1].step_type)

    def test_invalid_and_unreachable_inputs_return_contract_result(self):
        graph = _graph(("S", "G"))

        missing = bidirectional_search(graph, "missing", "G")
        unreachable = bidirectional_search(graph, "S", "G")

        for result in (missing, unreachable):
            self.assertIsInstance(result, SearchResult)
            self.assertFalse(result.success)
            self.assertEqual([], result.path)
            self.assertEqual(StepType.FINISH, result.steps[-1].step_type)

    def test_matches_reference_dijkstra_on_deterministic_directed_graphs(self):
        randomizer = random.Random(20260815)
        for graph_index in range(6):
            node_ids = tuple(f"N{index}" for index in range(18))
            graph = _graph(node_ids)
            # Always include a directed backbone, then add reproducible shortcuts.
            for index in range(len(node_ids) - 1):
                _add_directed_edge(
                    graph,
                    node_ids[index],
                    node_ids[index + 1],
                    randomizer.uniform(0.1, 5.0),
                )
            for source in node_ids:
                for target in node_ids:
                    if source != target and randomizer.random() < 0.11:
                        _add_directed_edge(
                            graph,
                            source,
                            target,
                            randomizer.uniform(0.1, 8.0),
                        )

            for _ in range(10):
                start, goal = randomizer.sample(node_ids, 2)
                expected = _reference_dijkstra(graph, start, goal)
                result = bidirectional_search(graph, start, goal)
                if math.isfinite(expected):
                    self.assertTrue(result.success, msg=f"graph={graph_index}")
                    self.assertTrue(
                        math.isclose(expected, result.total_cost, rel_tol=1e-9),
                        msg=f"graph={graph_index}, {start}->{goal}",
                    )
                else:
                    self.assertFalse(result.success, msg=f"graph={graph_index}")


if __name__ == "__main__":
    unittest.main()
