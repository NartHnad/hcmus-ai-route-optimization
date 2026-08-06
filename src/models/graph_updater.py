# src/models/graph_updater.py

from src.models import Graph


def update_single_edge_traffic(
    graph: Graph, from_node: str, to_node: str, congestion: float, risk: float
) -> bool:
    """
    Dynamically update the congestion and risk attributes of a single edge in-memory.
    Automatically recalculates actual travel time, normalized metrics, and edge weight.

    Args:
        graph (Graph): The active graph instance.
        from_node (str): Source node ID.
        to_node (str): Destination node ID.
        congestion (float): New congestion level (0.0 to 1.0).
        risk (float): New risk level (0.0 to 1.0).

    Returns:
        bool: True if edge was successfully updated, False if edge was not found.
    """
    edge = graph.get_edge(from_node, to_node)

    # Check existance
    if not edge:
        print(f"Edge not found: {from_node} -> {to_node}")
        return False

    # 1. Update user-selected congestion and risk attributes
    edge.congestion = float(congestion)
    edge.risk = float(risk)

    # 2. Recalculate dynamic travel time (Heavy congestion reduces travel speed by up to 70%)
    """
    Mức độ kẹt xe (congestion)  Trạng thái              speed_factor    Tốc độ còn lại
    0.0 (CLEAR)                 Thông thoáng            1.0             100% tốc độ gốc
    0.25 (LIGHT)                Đông nhẹ                0.825           82.5% tốc độ gốc
    0.50 (MODERATE)             Kẹt trung bình          0.65            65% tốc độ gốc
    0.75 (HEAVY)                Kẹt nặng                0.475           47.5% tốc độ gốc
    1.0 (GRIDLOCK)              Tắc nghẽn hoàn toàn     0.3             30% tốc độ gốc
    """
    speed_factor = max(0.1, 1.0 - (edge.congestion * 0.7))

    # Cache the original base travel time if not previously stored
    if not hasattr(edge, "_base_travel_time"):
        edge._base_travel_time = edge.travel_time

    # Calculate travel time
    edge.travel_time = edge._base_travel_time / speed_factor

    # 3. Normalize updated travel time against graph's maximum time metric
    safe_max_time = getattr(graph, "max_time", 1.0)
    edge.norm_travel_time = min(1.0, edge.travel_time / safe_max_time)

    # 4. Recalculate final composite edge weight (Cost Function)
    edge.weight = edge.calculate_cost()

    print(f"[UPDATED] Edge {from_node} <-> {to_node} | New Cost: {edge.weight:.4f}")
    return True
