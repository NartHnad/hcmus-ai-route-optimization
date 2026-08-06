from src.utils.distance import haversine_distance


def geographic_heuristic(graph, node_id, goal_id):
    """
    Straight-line Haversine distance (km) from node to goal.

    Admissible heuristic for informed search (A*, Greedy Best-First) when
    edge costs are distance-based. Returns 0.0 if either node is missing.
    """
    node = graph.get_node(node_id)
    goal = graph.get_node(goal_id)

    if node is None or goal is None:
        return 0.0

    return haversine_distance(node.lat, node.lon, goal.lat, goal.lon)
