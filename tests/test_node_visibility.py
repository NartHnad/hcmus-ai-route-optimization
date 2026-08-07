import unittest

# #NhatHuyChanged: regression tests for unnamed-node filtering.
from src.gui.map_widget import MapWidget
from src.models.models import Edge, Graph, Node
from src.utils.node_visibility import is_visible_node


class NodeVisibilityTests(unittest.TestCase):
    def test_named_road_node_is_visible(self):
        node = Node("1", "Giao Lê Đức Thọ × Đường số 27", 10.0, 106.0)

        self.assertTrue(is_visible_node(node))

    def test_unnamed_road_kind_is_hidden(self):
        node = Node(
            "2",
            "Nút trên đường chưa có tên",
            10.0,
            106.0,
            name_kind="unnamed_road",
        )

        self.assertFalse(is_visible_node(node))

    def test_name_with_missing_marker_is_hidden(self):
        node = Node("3", "Giao Đường số 8 × đường chưa có tên", 10.0, 106.0)

        self.assertFalse(is_visible_node(node))

    def test_generic_node_name_is_hidden(self):
        node = Node("4", "Node 31444008562 [intersection]", 10.0, 106.0)

        self.assertFalse(is_visible_node(node))


class MapSerializationVisibilityTests(unittest.TestCase):
    def test_edges_touching_hidden_nodes_are_marked_hidden(self):
        graph = Graph()
        graph.add_node(Node("A", "Đường A", 10.0, 106.0))
        graph.add_node(Node("B", "đường chưa có tên", 10.1, 106.1))
        graph.add_node(Node("C", "Đường C", 10.2, 106.2))
        graph.add_edge(
            Edge("A", "B", distance=1.0, travel_time=1.0, road_type="primary")
        )
        graph.add_edge(
            Edge("A", "C", distance=1.0, travel_time=1.0, road_type="primary")
        )

        payload = MapWidget._serialize_graph(None, graph)
        edge_visibility = {
            (edge["from"], edge["to"]): edge["visible"] for edge in payload["edges"]
        }

        self.assertFalse(edge_visibility[("A", "B")])
        self.assertFalse(edge_visibility[("B", "A")])
        self.assertTrue(edge_visibility[("A", "C")])
        self.assertTrue(edge_visibility[("C", "A")])
        self.assertEqual(payload["visible_nodes"], 2)
        self.assertEqual(payload["hidden_nodes"], 1)


if __name__ == "__main__":
    unittest.main()
