# src/graph_factory.py

import json
import os

from src.models.constants import RoadType, DEFAULT_SPEED_MAP, RiskLevel

try:
    from .models import Graph, Edge, Node
except ImportError:
    from models import Graph, Edge, Node

from src.data.traffic_update import generate_random_traffic_updates


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


def build_graph(json_path: str, traffic_updates: dict = None) -> Graph:
    """
    FACTORY PATTERN: Reads a JSON dataset containing both Nodes and Edges
    and converts it into a unified Graph structure to serve as the input for AI search algorithms.
    """
    # ======================
    # TEST TRAFFIC UPDATES
    # ======================
    traffic_updates = generate_random_traffic_updates(json_path, affected_ratio=0.2)
    # =====================

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

    temp_edges = []
    max_distance = 0.0
    max_time = 0.0

    # Initialize and Append all Edges
    for edge in data.get("edges", []):
        u = str(edge.get("u", edge.get("from"))).strip()
        v = str(edge.get("v", edge.get("to"))).strip()
        edge_key = f"{u}->{v}"

        distance_km = float(edge["distance"])
        road_type_str = str(edge.get("_str", "primary")).strip()

        # Calculate travel time if not provided,
        # using distance and average speed for the road type
        if "time" in edge or "travel_time" in edge:
            travel_time_min = float(edge.get("time", edge.get("travel_time")))
        else:
            speed_kmh = _get_road_speed(road_type_str)
            travel_time_min = (distance_km / speed_kmh) * 40.0

        congestion = float(edge.get("congestion", 1.0))
        risk = float(edge.get("risk", RiskLevel.NONE.value))

        # Real-time traffic / User overrides
        if edge_key in traffic_updates:
            override = traffic_updates[edge_key]
            congestion = float(override.get("congestion", congestion))
            risk = float(override.get("risk", risk))

        new_edge = Edge(
            from_node=u,
            to_node=v,
            distance=distance_km,
            travel_time=travel_time_min,
            road_type=road_type_str,
            is_one_way=edge.get("is_one_way", False),
            congestion=congestion,
            risk=risk,
            note=edge.get("note", ""),
        )

        # UPDATES MAX DISTANCE & MAX TIME
        max_distance = max(max_distance, distance_km)
        max_time = max(max_time, travel_time_min)

        temp_edges.append(new_edge)

    # Save max distance to the graph
    graph.max_distance = max_distance if max_distance > 0 else 1.0

    # max time
    safe_max_time = max_time if max_time > 0 else 1.0

    # Normalize distance and travel time for all edges, and calculate their cost
    for edge in temp_edges:
        # Normalize value to [0.0, 1.0]
        edge.norm_distance = edge.distance / graph.max_distance
        edge.norm_time = edge.travel_time / safe_max_time

        # Calculate normalized cost and store it in edge.weight
        edge.weight = edge.calculate_cost()

        graph.add_edge(edge)

    print(f"[FACTORY SUCCESS] Added {len(graph.nodes)} nodes and paths into Graph.")
    print(
        f"[METRICS] Max Distance: {max_distance:.2f} km | Max Time: {max_time:.2f} mins"
    )

    return graph
