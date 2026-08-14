import heapq
import math

from src.models.models import SearchResult, SearchStep, StepType


def haversine_distance(lat1, lon1, lat2, lon2):
    """Return the great-circle distance between two coordinates in kilometres."""
    if None in (lat1, lon1, lat2, lon2):
        return 0.0

    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    a = min(1.0, max(0.0, a))
    return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def beam_search(graph, start_id, goal_id, beam_width=10, mode="optimal"):
    """Find a route using bounded-width best-first beam search.

    Beam search is not guaranteed to find a path or an optimal path because
    candidates outside the beam are deliberately pruned.
    """
    steps = []
    visited_order = []

    if not isinstance(beam_width, int) or beam_width <= 0:
        raise ValueError("beam_width must be a positive integer")

    if graph is None or start_id not in graph.nodes or goal_id not in graph.nodes:
        steps.append(SearchStep(StepType.FINISH))
        return SearchResult(
            path=[],
            steps=steps,
            total_cost=0.0,
            visited_order=visited_order,
            success=False,
            message="Graph is not loaded or start/goal node not found.",
        )

    goal_node = graph.get_node(goal_id)

    def heuristic(node_id):
        # Geographic distance is comparable to edge distance only in shortest
        # mode. Other modes combine different units, so no safe h estimate is
        # available without a speed/penalty model.
        if mode != "shortest":
            return 0.0

        node = graph.get_node(node_id)
        if node is None or goal_node is None:
            return 0.0
        return haversine_distance(node.lat, node.lon, goal_node.lat, goal_node.lon)

    def build_success_result():
        path = []
        path_edges = []
        cursor = goal_id

        while cursor is not None:
            path.append(cursor)
            parent, edge_to_cursor = came_from[cursor]
            if edge_to_cursor is not None:
                path_edges.append(edge_to_cursor)
            cursor = parent

        path.reverse()
        path_edges.reverse()
        total_cost = sum(edge.calculate_cost() for edge in path_edges)
        steps.append(SearchStep(StepType.FINISH, node_id=goal_id))

        return SearchResult(
            path=path,
            steps=steps,
            total_cost=total_cost,
            visited_order=visited_order,
            success=True,
            message=(
                f"Beam Search (beam_width={beam_width}) found a path after "
                f"exploring {len(visited_order)} node(s)."
            ),
        )

    current_beam = [start_id]
    discovered = {start_id}
    came_from = {start_id: (None, None)}
    path_cost = {start_id: 0.0}

    while current_beam:
        candidate_by_node = {}

        for current in current_beam:
            visited_order.append(current)
            steps.append(SearchStep(StepType.EXPAND, node_id=current))

            if current == goal_id:
                return build_success_result()

            for edge in graph.get_neighbors(current):
                neighbor = edge.to_node
                if neighbor in discovered:
                    continue

                edge_cost = edge.calculate_cost()
                tentative_g = path_cost[current] + edge_cost
                f = tentative_g + heuristic(neighbor)
                candidate = (f, tentative_g, neighbor, current, edge)

                previous = candidate_by_node.get(neighbor)
                if previous is None or candidate[:2] < previous[:2]:
                    candidate_by_node[neighbor] = candidate

        if not candidate_by_node:
            break

        next_candidates = heapq.nsmallest(
            beam_width,
            candidate_by_node.values(),
            key=lambda candidate: candidate[:3],
        )

        current_beam = []
        for priority, tentative_g, neighbor, parent, edge in next_candidates:
            discovered.add(neighbor)
            came_from[neighbor] = (parent, edge)
            path_cost[neighbor] = tentative_g
            current_beam.append(neighbor)
            steps.append(
                SearchStep(
                    StepType.DISCOVER,
                    node_id=neighbor,
                    edge_from=parent,
                    edge_to=neighbor,
                    metrics={"g": tentative_g, "h": heuristic(neighbor), "f": priority},
                )
            )

    # There is no complete route to price when the goal is not reached.
    total_cost = 0.0
    steps.append(
        SearchStep(
            StepType.FINISH,
            metrics={"total_cost": total_cost},
        )
    )
    return SearchResult(
        path=[],
        steps=steps,
        total_cost=total_cost,
        visited_order=visited_order,
        success=False,
        message=(
            f"No path found within beam width {beam_width} from "
            f"'{start_id}' to '{goal_id}'."
        ),
    )
