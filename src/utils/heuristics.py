from src.utils.distance import haversine_distance


def geographic_heuristic(graph, node_id, goal_id, alpha: float = 0.25) -> float:
    """
    Admissible lower bound of the normalized composite edge cost.

    h(n) = alpha * haversine(node, goal) / graph.max_distance

    Edge cost = alpha * norm_distance + beta * norm_travel_time
              + gamma * congestion + delta * risk

    The distance term is the only one with a known nonzero lower bound:
    total remaining road distance >= straight-line distance. Time,
    congestion and risk are all >= 0, so dropping them keeps h admissible.
    `alpha` must match the weight used by Edge.calculate_cost().
    """
    node = graph.get_node(node_id)
    goal = graph.get_node(goal_id)

    if node is None or goal is None:
        return 0.0

    distance_km = haversine_distance(node.lat, node.lon, goal.lat, goal.lon)

    max_distance = max(float(getattr(graph, "max_distance", 1.0)), 1e-12)

    return alpha * (distance_km / max_distance)
