# src/graph_factory.py

import json
import os
from models import Graph, Edge, Node


def build_graph(json_path: str) -> Graph:
    """ 
    FACTORY PATTERN: Reads a JSON dataset containing both Nodes and Edges 
    and converts it into a unified Graph structure to serve as the input for AI search algorithms.
    """

    # Check file exists
    if not os.path.exists(json_path):
        raise FileExistsError(f"Not found dataset file {json_path}")

    # Read data from json file
    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Initialize a Graph object
    graph = Graph()

    # Initialize and Append all Nodes
    for node in data.get("nodes", []):
        new_node = Node(
            node_id=node["id"].strip(),
            name=node["name"].strip(),
            x=float(node["x"]),
            y=float(node["y"]),
        )
        graph.add_node(new_node)

    # Initialize and Append all Edges
    for edge in data.get("edges", []):
        new_edge = Edge(
            from_node=edge["from"].strip(),
            to_node=edge["to"].strip(),
            distance=float(edge["distance"]),
            travel_time=float(edge["travel_time"]),
            road_type=edge["road_type"].strip(),
            direction=edge["direction"].strip().lower(),
            # Using get to assign default value when miss data
            congestion=int(edge.get("congestion", 1)),
            flooding=int(edge.get("flooding", 1)),
        )
        graph.add_edge(new_edge)

    print(f"[FACTORY SUCCESS] Added {len(graph.nodes)} nodes and paths into Graph.")

    return graph
