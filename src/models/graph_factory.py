# src/graph_factory.py

import json
import os

from src.constants import RoadType, DEFAULT_SPEED_MAP, CongestionLevel, RiskLevel

try:
    from .models import Graph, Edge, Node
except ImportError:
    from models import Graph, Edge, Node

from src.data.traffic_update import generate_random_traffic_updates


"""
có nhiệm vụ đọc dữ liệu JSON và biến nó thành object Graph để các thuật toán sử dụng.

File JSON thô
    ↓
graph_factory
    ├── tạo Node
    ├── tạo Edge
    ├── tính thời gian nếu thiếu
    ├── chuẩn hóa khoảng cách/thời gian
    ├── tính cost
    └── xử lý đường một chiều/hai chiều
    ↓
Graph hoàn chỉnh
    ↓
BFS, DFS, UCS, A*, GA, SA...
"""

def _get_road_speed(road_type: str) -> float:
    """
    Retrieve the average speed for a given road type.
    If the road type is not recognized, return a default speed of 30 km/h.
    """
    
    """
    Lấy tốc độ trung bình dựa trên loại đường
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
    graph = Graph() # tạo 1 graph rỗng

    # Initialize and Append all Nodes
    for node in _iter_nodes(data.get("nodes", [])): # biến dữ liệu json thành các node
        new_node = Node(
            node_id=node["id"].strip(),
            name=node["name"].strip(),
            lat=float(node.get("lat", node.get("x"))),
            lon=float(node.get("lon", node.get("y"))),
            node_type=node.get("type", "intersection"),
        )
        graph.add_node(new_node) # thêm node vào graph, đồng thời tạo luôn danh sách cạnh cho mỗi node

    temp_edges = []
    max_distance = 0.0
    max_time = 0.0

    # Initialize and Append all Edges
    for edge in data.get("edges", []):
        u = str(edge.get("u", edge.get("from"))).strip()
        v = str(edge.get("v", edge.get("to"))).strip()

        distance_km = float(edge["distance"])
        road_type_str = str(edge.get("road_type", "primary")).strip()

        # Tính travel_time nếu không được cung cấp, nếu data có rồi thì dùng luôn
        if "time" in edge or "travel_time" in edge:
            travel_time_min = float(edge.get("time", edge.get("travel_time")))
        else:
            speed_kmh = _get_road_speed(road_type_str)
            travel_time_min = (distance_km / speed_kmh) * 60.0

        # Base congestion and risk
        congestion = float(edge.get("congestion", CongestionLevel.CLEAR.value))
        risk = float(edge.get("risk", RiskLevel.NONE.value))

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
    # Safer Max time to divide
    graph.max_time = max_time if max_time > 0 else 1.0

    # Normalize distance and travel time for all edges, and calculate their cost
    for edge in temp_edges:
        # Normalize value to [0.0, 1.0]
        edge.norm_distance = edge.distance / graph.max_distance
        edge.norm_travel_time = edge.travel_time / graph.max_time

        # Calculate normalized cost and store it in edge.weight
        edge.weight = edge.calculate_cost()

        graph.add_edge(edge) # Xử lý đường 1 chiều và 2 chiều

    print(f"[FACTORY SUCCESS] Added {len(graph.nodes)} nodes and paths into Graph.")
    print(
        f"[METRICS] Max Distance: {max_distance:.2f} km | Max Time: {max_time:.2f} mins"
    )

    return graph    
