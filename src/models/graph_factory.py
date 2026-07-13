# src/graph_factory.py

import json
import os

try:
    from .models import Graph, Edge, Node
except ImportError:
    from models import Graph, Edge, Node


def _iter_nodes(raw_nodes):
    if isinstance(raw_nodes, dict):
        return raw_nodes.values()
    return raw_nodes or []


def _edge_is_oneway(edge: dict) -> bool:
    if "is_oneway" in edge:
        return bool(edge["is_oneway"])

    direction = str(edge.get("direction", "one-way")).strip().lower()
    return direction != "two-way"


def _should_auto_reverse(edge: dict) -> bool:
    """
    Legacy map_data.json stores two-way roads as one edge with direction='two-way'.
    mock_data.json stores each direction explicitly using u/v and is_oneway.
    """
    if "is_oneway" in edge:
        return False

    direction = str(edge.get("direction", "one-way")).strip().lower()
    return direction == "two-way"


def build_graph(json_path: str) -> Graph:
    """
    FACTORY PATTERN: Reads a JSON dataset containing both Nodes and Edges
    and converts it into a unified Graph structure to serve as the input for AI search algorithms.
    """

    # Check file exists
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Not found dataset file {json_path}")

    # Read data from json file
    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Initialize a Graph object
    graph = Graph()

    # Initialize and Append all Nodes
    for node in _iter_nodes(data.get("nodes", [])):
        new_node = Node(
            node_id=node["id"].strip(),
            name=node["name"].strip(),
            lat=float(node.get("lat", node.get("x"))),
            lon=float(node.get("lon", node.get("y"))),
            node_type=node.get("type", "intersection"),
        )
        graph.add_node(new_node)

    # Initialize and Append all Edges
    for edge in data.get("edges", []):
        new_edge = Edge(
            from_node=edge.get("u", edge.get("from")).strip(),
            to_node=edge.get("v", edge.get("to")).strip(),
            distance=float(edge["distance"]),
            travel_time=float(edge.get("time", edge.get("travel_time"))),
            road_type=edge["road_type"].strip(),
            is_oneway=_edge_is_oneway(edge),
            congestion=int(edge.get("congestion", 1)),
            risk=int(edge.get("risk", edge.get("flooding", 1))),
            note=edge.get("note", ""),
        )
        graph.add_edge(new_edge, auto_reverse=_should_auto_reverse(edge))

    print(f"[FACTORY SUCCESS] Added {len(graph.nodes)} nodes and paths into Graph.")

    return graph
