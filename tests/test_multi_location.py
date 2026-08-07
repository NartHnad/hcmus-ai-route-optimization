# #NhatHuyChanged: regression tests for the multi-location route optimizer.
import unittest

from src.algorithms.multi_location import (
    multi_location_nearest_neighbor_2opt,
    nearest_neighbor_order,
    two_opt,
)
from src.models.models import Edge, Graph, Node


class MultiLocationAlgorithmTests(unittest.TestCase):
    def setUp(self):
        self.graph = Graph()
        for node_id in ("S", "A", "B", "G"):
            self.graph.add_node(Node(node_id, node_id, 10.0, 106.0))

        # A directed complete graph makes route-order assertions deterministic.
        distances = {
            ("S", "A"): 1,
            ("S", "B"): 2,
            ("S", "G"): 20,
            ("A", "B"): 10,
            ("A", "G"): 2,
            ("B", "A"): 1,
            ("B", "G"): 10,
        }
        for (source, target), distance in distances.items():
            self.graph.add_edge(
                Edge(source, target, distance, distance, "primary", is_one_way=True)
            )

    def test_nearest_neighbor_and_two_opt_helpers(self):
        costs = {
            ("S", "A"): 1,
            ("S", "B"): 2,
            ("A", "B"): 10,
            ("A", "G"): 2,
            ("B", "A"): 1,
            ("B", "G"): 10,
        }
        initial = nearest_neighbor_order("S", ["A", "B"], costs, end_id="G")
        self.assertEqual(initial, ["S", "A", "B", "G"])
        optimized, cost, swaps = two_opt(initial, costs, fixed_end=True)
        self.assertEqual(optimized, ["S", "B", "A", "G"])
        self.assertLess(cost, 23)
        self.assertGreaterEqual(swaps, 1)

    def test_multi_location_returns_graph_path_and_fixed_goal(self):
        result = multi_location_nearest_neighbor_2opt(
            self.graph, "S", ["A", "B"], end_id="G"
        )
        self.assertTrue(result.success)
        self.assertEqual(result.visited_order[0], "S")
        self.assertEqual(result.visited_order[-1], "G")
        self.assertTrue({"A", "B"}.issubset(result.visited_order))
        self.assertEqual(result.path[0], "S")
        self.assertEqual(result.path[-1], "G")

    def test_unknown_location_fails_without_throwing(self):
        result = multi_location_nearest_neighbor_2opt(
            self.graph, "S", ["NOT_IN_GRAPH"], end_id="G"
        )
        self.assertFalse(result.success)
        self.assertIn("Unknown", result.message)


if __name__ == "__main__":
    unittest.main()
