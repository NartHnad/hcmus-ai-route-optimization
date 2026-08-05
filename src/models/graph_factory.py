# src/graph_factory.py

import json
import os

from constants import RoadType, DEFAULT_SPEED_MAP, RiskLevel

try:
    from .models import Graph, Edge, Node
except ImportError:
    from models import Graph, Edge, Node


def _get_road_speed(road_type: str) -> float:
    """
    Retrieve the average speed for a given road type.
    If the road type is not recognized, return a default speed of 30 km/h.
    """
    try:
        road_enum = RoadType(road_type.lower())
        return DEFAULT_SPEED_MAP.get(road_enum, 30.0)
    except ValueError:
        # If the road type is not in the RoadType enum, return default speed
        return 30.0


def _iter_nodes(raw_nodes):
    if isinstance(raw_nodes, dict):
        return raw_nodes.values()
    return raw_nodes or []


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
            road_type=edge["road_type"].strip(),
            travel_time=float(edge.get("time", edge.get("travel_time"))),
            is_one_way=edge.get("is_one_way", False),
            congestion=int(edge.get("congestion", 1)),
            risk=int(edge.get("risk", 0)),
            note=edge.get("note", ""),
        )
        graph.add_edge(new_edge)

    print(f"[FACTORY SUCCESS] Added {len(graph.nodes)} nodes and paths into Graph.")

    return graph
