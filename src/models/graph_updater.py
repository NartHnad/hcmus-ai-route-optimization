"""Validated, in-memory updates for editable graph edges."""

import math

from src.models.models import Graph


class EdgeUpdateError(ValueError):
    """Raised when an edge update request is invalid."""


def _finite_float(value, field_name):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EdgeUpdateError(f"{field_name} must be a number.") from exc
    if not math.isfinite(number):
        raise EdgeUpdateError(f"{field_name} must be finite.")
    return number


def edge_direction_payload(edge):
    """Serialize one directed edge for the web-based editors."""
    return {
        "from": edge.from_node,
        "to": edge.to_node,
        "distance": edge.distance,
        "travel_time": edge.travel_time,
        "risk": edge.risk,
        "congestion": edge.congestion,
        "road_type": edge.road_type,
        "note": edge.note,
        "cost": edge.calculate_cost(),
    }


def serialize_visual_edges(graph):
    """Deduplicate physical roads while retaining per-direction attributes."""
    visual_edges = {}
    direction_sets = {}
    for outgoing_edges in graph.adjacency_list.values():
        for edge in outgoing_edges:
            pair = tuple(sorted((edge.from_node, edge.to_node)))
            if pair not in visual_edges:
                detail = edge_direction_payload(edge)
                visual_edges[pair] = {
                    **detail,
                    "directions": [],
                    "direction_details": [],
                }
                direction_sets[pair] = set()
            direction = (edge.from_node, edge.to_node)
            if direction in direction_sets[pair]:
                continue
            direction_sets[pair].add(direction)
            visual_edges[pair]["directions"].append(list(direction))
            visual_edges[pair]["direction_details"].append(
                edge_direction_payload(edge)
            )
    return list(visual_edges.values())


def update_edge_attributes(
    graph: Graph,
    from_node: str,
    to_node: str,
    travel_time,
    risk,
    congestion,
):
    """Atomically update editable attributes of one directed edge.

    Distance and metadata are deliberately absent from this API so callers
    cannot change immutable fields through the edge editor.
    """
    if graph is None:
        raise EdgeUpdateError("No graph is loaded.")
    edge = graph.get_edge(str(from_node), str(to_node))
    if edge is None:
        raise EdgeUpdateError(f"Edge {from_node} -> {to_node} was not found.")

    new_time = _finite_float(travel_time, "Estimated time")
    new_risk = _finite_float(risk, "Risk")
    new_congestion = _finite_float(congestion, "Congestion")
    if new_time <= 0:
        raise EdgeUpdateError("Estimated time must be greater than 0.")
    if not 0.0 <= new_risk <= 1.0:
        raise EdgeUpdateError("Risk must be between 0 and 1.")
    if not 0.0 <= new_congestion <= 1.0:
        raise EdgeUpdateError("Congestion must be between 0 and 1.")

    safe_max_time = max(
        _finite_float(getattr(graph, "max_time", 1.0), "Maximum time"),
        1e-12,
    )

    edge.travel_time = new_time
    edge.risk = new_risk
    edge.congestion = new_congestion
    edge.norm_travel_time = min(1.0, max(0.0, new_time / safe_max_time))
    edge.weight = edge.calculate_cost()
    return edge_direction_payload(edge)


def update_single_edge_traffic(
    graph: Graph, from_node: str, to_node: str, congestion: float, risk: float
) -> bool:
    """Backward-compatible dynamic traffic update."""
    edge = graph.get_edge(from_node, to_node) if graph is not None else None
    if edge is None:
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
    return True
