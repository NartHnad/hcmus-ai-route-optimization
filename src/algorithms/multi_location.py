# #NhatHuyChanged: add multi-location Nearest Neighbor + 2-Opt optimizer.
"""Multi-location route optimization using Nearest Neighbor and 2-Opt.

The graph contains road-segment edges while the user selects landmark nodes.
Consequently, the optimizer first computes shortest graph paths between the
selected locations and then optimizes the order of those locations.  The
returned path is the concatenation of the selected shortest paths, so it can
be consumed by the existing ``SearchResult``/Leaflet animation contract.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Iterable, Mapping, Sequence

from src.constants import StepType
from src.models.models import SearchResult, SearchStep


ALGORITHM_NAME = "Multi-location (Nearest Neighbor + 2-Opt)"


def _edge_cost(edge) -> float:
    """Return the same weighted cost used by the existing search algorithms.

    Hand-built graphs in tests may not have normalized values yet.  Falling
    back to physical distance keeps the optimizer useful for those graphs.
    """

    cost = float(edge.calculate_cost())
    if cost > 0.0:
        return cost
    return float(edge.distance)


def _shortest_path(graph, source: str, target: str):
    """Dijkstra shortest path for one pair, returning ``(cost, path)``."""

    if source not in graph.nodes or target not in graph.nodes:
        return math.inf, []
    if source == target:
        return 0.0, [source]

    frontier = [(0.0, source)]
    distances = {source: 0.0}
    parents = {source: None}

    while frontier:
        current_cost, current = heapq.heappop(frontier)
        if current_cost > distances.get(current, math.inf):
            continue
        if current == target:
            path = []
            cursor = target
            while cursor is not None:
                path.append(cursor)
                cursor = parents[cursor]
            path.reverse()
            return current_cost, path

        for edge in graph.get_neighbors(current):
            candidate = current_cost + _edge_cost(edge)
            if candidate < distances.get(edge.to_node, math.inf):
                distances[edge.to_node] = candidate
                parents[edge.to_node] = current
                heapq.heappush(frontier, (candidate, edge.to_node))

    return math.inf, []


def _normalise_locations(locations) -> list[str]:
    if locations is None:
        return []
    if isinstance(locations, str):
        locations = locations.replace(";", ",").split(",")
    return [str(location).strip() for location in locations if str(location).strip()]


def nearest_neighbor_order(
    start_id: str,
    locations: Sequence[str],
    costs: Mapping[tuple[str, str], float],
    end_id: str | None = None,
) -> list[str] | None:
    """Build a route order by repeatedly choosing the nearest unvisited stop."""

    remaining = list(dict.fromkeys(locations))
    route = [start_id]
    current = start_id

    while remaining:
        candidates = [
            location
            for location in remaining
            if math.isfinite(costs.get((current, location), math.inf))
        ]
        if not candidates:
            return None
        next_location = min(
            candidates,
            key=lambda location: (costs[(current, location)], str(location)),
        )
        route.append(next_location)
        remaining.remove(next_location)
        current = next_location

    if end_id is not None:
        if not math.isfinite(costs.get((current, end_id), math.inf)):
            return None
        route.append(end_id)

    return route


def _route_cost(route: Sequence[str], costs: Mapping[tuple[str, str], float]) -> float:
    return sum(
        costs.get((route[index], route[index + 1]), math.inf)
        for index in range(len(route) - 1)
    )


def two_opt(
    route: Sequence[str],
    costs: Mapping[tuple[str, str], float],
    *,
    fixed_end: bool = False,
    max_iterations: int = 100,
) -> tuple[list[str], float, int]:
    """Improve a route with first-improvement 2-Opt swaps.

    The first node is always fixed.  ``fixed_end`` also protects the last
    node (the selected Goal), while a closed route naturally protects its
    repeated start node by passing ``fixed_end=True``.
    """

    best = list(route)
    best_cost = _route_cost(best, costs)
    if len(best) < 4 or not math.isfinite(best_cost):
        return best, best_cost, 0

    iterations = 0
    last_swappable = len(best) - 2 if fixed_end else len(best) - 1
    while iterations < max_iterations:
        improved = False
        for left in range(1, last_swappable):
            for right in range(left + 1, last_swappable + 1):
                candidate = best[:left] + best[left : right + 1][::-1] + best[right + 1 :]
                candidate_cost = _route_cost(candidate, costs)
                if candidate_cost + 1e-12 < best_cost:
                    best, best_cost = candidate, candidate_cost
                    iterations += 1
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break
    return best, best_cost, iterations


def multi_location_nearest_neighbor_2opt(
    graph,
    start_id: str,
    locations: Iterable[str] | str,
    *,
    end_id: str | None = None,
    return_to_start: bool = False,
    two_opt_iterations: int = 100,
) -> SearchResult:
    """Optimize a route through multiple locations.

    ``locations`` are intermediate/required stops.  When ``end_id`` is
    provided it is appended after the optimized stops and remains fixed.  A
    closed tour can be requested with ``return_to_start=True`` when no fixed
    end is needed.
    """

    steps: list[SearchStep] = []
    if graph is None or start_id not in graph.nodes:
        return SearchResult(
            steps=[SearchStep(StepType.FINISH, node_id=None)],
            success=False,
            message="Graph is not loaded or the start node was not found.",
        )

    stop_ids = _normalise_locations(locations)
    if end_id is not None:
        end_id = str(end_id).strip()
        if end_id:
            stop_ids = [stop for stop in stop_ids if stop != end_id]
    stop_ids = [stop for stop in dict.fromkeys(stop_ids) if stop != start_id]
    requested_ids = stop_ids + ([end_id] if end_id else [])
    missing = [node_id for node_id in requested_ids if node_id not in graph.nodes]
    if missing:
        return SearchResult(
            steps=[SearchStep(StepType.FINISH, node_id=None)],
            success=False,
            message=f"Unknown location node(s): {', '.join(missing)}.",
        )

    if not stop_ids and not end_id:
        path = [start_id]
        if return_to_start:
            path.append(start_id)
        steps.append(SearchStep(StepType.FINISH, node_id=start_id))
        return SearchResult(
            path=path,
            steps=steps,
            success=True,
            message="Multi-location route contains no additional stops.",
            visited_order=[start_id],
        )

    all_locations = [start_id] + stop_ids + ([end_id] if end_id else [])
    costs: dict[tuple[str, str], float] = {}
    paths: dict[tuple[str, str], list[str]] = {}
    for source in all_locations:
        for target in all_locations:
            if source == target:
                costs[(source, target)] = 0.0
                paths[(source, target)] = [source]
            else:
                pair_cost, pair_path = _shortest_path(graph, source, target)
                costs[(source, target)] = pair_cost
                paths[(source, target)] = pair_path

    order = nearest_neighbor_order(start_id, stop_ids, costs, end_id=end_id)
    if order is None:
        steps.append(SearchStep(StepType.FINISH, node_id=None))
        return SearchResult(
            steps=steps,
            success=False,
            message="No reachable route covers all selected locations.",
        )

    if return_to_start and end_id is None:
        return_cost = costs.get((order[-1], start_id), math.inf)
        if not math.isfinite(return_cost):
            return SearchResult(
                steps=[SearchStep(StepType.FINISH, node_id=None)],
                success=False,
                message="The selected locations cannot form a closed tour.",
            )
        order.append(start_id)

    optimized_order, optimized_cost, swap_count = two_opt(
        order,
        costs,
        fixed_end=end_id is not None or return_to_start,
        max_iterations=max(0, int(two_opt_iterations)),
    )

    final_path: list[str] = []
    for source, target in zip(optimized_order, optimized_order[1:]):
        segment = paths.get((source, target), [])
        if not segment:
            return SearchResult(
                steps=[SearchStep(StepType.FINISH, node_id=None)],
                success=False,
                message=f"No road path exists from '{source}' to '{target}'.",
            )
        if not final_path:
            final_path.extend(segment)
        else:
            final_path.extend(segment[1:])

    for source, target in zip(optimized_order, optimized_order[1:]):
        steps.append(
            SearchStep(
                StepType.UPDATE,
                node_id=target,
                edge_from=source,
                edge_to=target,
                metrics={"stage": "nearest_neighbor"},
            )
        )
    if swap_count:
        steps.append(
            SearchStep(
                StepType.UPDATE,
                node_id=optimized_order[-1],
                metrics={
                    "stage": "2-opt",
                    "swaps": swap_count,
                    "initial_cost": _route_cost(order, costs),
                    "optimized_cost": optimized_cost,
                },
            )
        )
    steps.append(
        SearchStep(
            StepType.FINISH,
            node_id=optimized_order[-1],
            metrics={"stops": len(optimized_order) - 1, "2opt_swaps": swap_count},
        )
    )

    return SearchResult(
        path=final_path,
        steps=steps,
        total_cost=optimized_cost,
        success=True,
        message=(
            f"Multi-location route optimized through {len(optimized_order) - 1} "
            f"location(s) using Nearest Neighbor + 2-Opt ({swap_count} swap(s))."
        ),
        visited_order=optimized_order,
    )


multi_location = multi_location_nearest_neighbor_2opt
