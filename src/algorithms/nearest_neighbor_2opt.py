# #NhatHuyChanged: implement the production multi-location NN + 2-Opt route optimizer.
"""Multi-location routing with Nearest Neighbor followed by 2-Opt.

The optimizer works on a metric closure of the selected locations: shortest
road-network costs are calculated between the start and every goal, Nearest
Neighbor builds a deterministic initial order, and 2-Opt improves that open
route while keeping the start fixed. The final result contains the complete
road-node path so the existing map and graph renderers can animate it.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Mapping, Sequence

from src.constants import StepType
from src.models.models import SearchResult, SearchStep


ALGORITHM_NAME = "Nearest Neighbor + 2-Opt"
_EPSILON = 1e-12


def _edge_cost(edge) -> float:
    """Return a non-negative edge cost compatible with project algorithms."""

    cost = float(edge.calculate_cost())
    if not math.isfinite(cost) or cost < 0.0:
        return math.inf
    if cost > 0.0:
        return cost

    # Hand-built graphs used in tests may not have normalized values yet.
    # Physical distance is a safe deterministic fallback in that situation.
    distance = float(getattr(edge, "distance", 0.0))
    return distance if math.isfinite(distance) and distance >= 0.0 else math.inf


def _normalize_goals(goal_ids) -> list[str]:
    if goal_ids is None:
        return []
    if isinstance(goal_ids, str):
        goal_ids = goal_ids.replace(";", ",").split(",")
    return [str(goal).strip() for goal in goal_ids if str(goal).strip()]


def _shortest_costs_from(graph, source: str, targets: Sequence[str]) -> dict[str, float]:
    """Run one multi-target Dijkstra search from ``source``."""

    requested = set(targets)
    requested.discard(source)
    found: dict[str, float] = {}
    distances = {source: 0.0}
    frontier = [(0.0, source)]
    settled = set()

    while frontier and requested:
        current_cost, current = heapq.heappop(frontier)
        if current in settled or current_cost > distances.get(current, math.inf):
            continue
        settled.add(current)

        if current in requested:
            found[current] = current_cost
            requested.remove(current)

        for edge in graph.get_neighbors(current):
            edge_cost = _edge_cost(edge)
            if not math.isfinite(edge_cost):
                continue
            candidate = current_cost + edge_cost
            if candidate + _EPSILON < distances.get(edge.to_node, math.inf):
                distances[edge.to_node] = candidate
                heapq.heappush(frontier, (candidate, edge.to_node))

    return {target: found.get(target, math.inf) for target in targets}


def _shortest_path(graph, source: str, target: str) -> tuple[float, list[str]]:
    """Return the exact lowest-cost road path for one final route leg."""

    if source == target:
        return 0.0, [source]

    distances = {source: 0.0}
    parents = {source: None}
    frontier = [(0.0, source)]
    settled = set()

    while frontier:
        current_cost, current = heapq.heappop(frontier)
        if current in settled or current_cost > distances.get(current, math.inf):
            continue
        settled.add(current)

        if current == target:
            path = []
            cursor = target
            while cursor is not None:
                path.append(cursor)
                cursor = parents[cursor]
            path.reverse()
            return current_cost, path

        for edge in graph.get_neighbors(current):
            edge_cost = _edge_cost(edge)
            if not math.isfinite(edge_cost):
                continue
            candidate = current_cost + edge_cost
            if candidate + _EPSILON < distances.get(edge.to_node, math.inf):
                distances[edge.to_node] = candidate
                parents[edge.to_node] = current
                heapq.heappush(frontier, (candidate, edge.to_node))

    return math.inf, []


def build_cost_matrix(graph, locations: Sequence[str]) -> dict[tuple[str, str], float]:
    """Build directed shortest-path costs using one graph search per location."""

    unique_locations = list(dict.fromkeys(locations))
    costs: dict[tuple[str, str], float] = {}
    for source in unique_locations:
        targets = [target for target in unique_locations if target != source]
        source_costs = _shortest_costs_from(graph, source, targets)
        costs[(source, source)] = 0.0
        for target in targets:
            costs[(source, target)] = source_costs[target]
    return costs


def route_cost(route: Sequence[str], costs: Mapping[tuple[str, str], float]) -> float:
    """Return the directed cost of an open route."""

    total = 0.0
    for source, target in zip(route, route[1:]):
        leg_cost = costs.get((source, target), math.inf)
        if not math.isfinite(leg_cost):
            return math.inf
        total += leg_cost
    return total


def nearest_neighbor_order(
    start_id: str,
    goal_ids: Sequence[str],
    costs: Mapping[tuple[str, str], float],
) -> list[str] | None:
    """Create a deterministic nearest-neighbor order with a fixed start."""

    remaining = list(goal_ids)
    input_rank = {goal: index for index, goal in enumerate(remaining)}
    order = [start_id]
    current = start_id

    while remaining:
        reachable = [
            goal
            for goal in remaining
            if math.isfinite(costs.get((current, goal), math.inf))
        ]
        if not reachable:
            return None
        next_goal = min(
            reachable,
            key=lambda goal: (
                costs[(current, goal)],
                input_rank[goal],
                str(goal),
            ),
        )
        order.append(next_goal)
        remaining.remove(next_goal)
        current = next_goal

    return order


def two_opt(
    route: Sequence[str],
    costs: Mapping[tuple[str, str], float],
    max_iterations: int = 100,
) -> tuple[list[str], float, list[dict]]:
    """Improve an open, directed route while keeping index zero fixed.

    Candidate costs are recomputed in full. This is slightly more work than
    the symmetric four-edge shortcut but remains correct for one-way roads.
    Best-improvement selection makes the result deterministic.
    """

    best = list(route)
    best_cost = route_cost(best, costs)
    improvements: list[dict] = []
    if len(best) < 3 or not math.isfinite(best_cost):
        return best, best_cost, improvements

    for iteration in range(1, max(0, int(max_iterations)) + 1):
        iteration_best = None
        for left in range(1, len(best) - 1):
            for right in range(left + 1, len(best)):
                candidate = (
                    best[:left]
                    + list(reversed(best[left : right + 1]))
                    + best[right + 1 :]
                )
                candidate_cost = route_cost(candidate, costs)
                if candidate_cost + _EPSILON >= best_cost:
                    continue
                candidate_key = (
                    candidate_cost,
                    tuple(map(str, candidate)),
                    left,
                    right,
                )
                if iteration_best is None or candidate_key < iteration_best[0]:
                    iteration_best = (
                        candidate_key,
                        candidate,
                        candidate_cost,
                        left,
                        right,
                    )

        if iteration_best is None:
            break

        _, candidate, candidate_cost, left, right = iteration_best
        previous_cost = best_cost
        best = candidate
        best_cost = candidate_cost
        improvements.append(
            {
                "iteration": iteration,
                "left": left,
                "right": right,
                "previous_cost": previous_cost,
                "optimized_cost": best_cost,
                "route": list(best),
            }
        )

    return best, best_cost, improvements


def _failure(message: str, node_id: str | None = None, **metrics) -> SearchResult:
    finish_metrics = {"success": False, **metrics}
    return SearchResult(
        path=[],
        steps=[SearchStep(StepType.FINISH, node_id=node_id, metrics=finish_metrics)],
        total_cost=0.0,
        success=False,
        message=message,
    )


def nearest_neighbor_2opt(
    graph,
    start_id: str,
    goal_ids,
    respect_goal_order: bool = False,
    max_two_opt_iterations: int = 100,
) -> SearchResult:
    """Visit every goal once using Nearest Neighbor followed by 2-Opt."""

    goals = _normalize_goals(goal_ids)
    if graph is None or start_id not in getattr(graph, "nodes", {}):
        return _failure("Graph or start node is invalid.", stage="validation")
    if not goals:
        return _failure("At least one goal is required.", start_id, stage="validation")
    if len(set(goals)) != len(goals):
        return _failure("Goal nodes must be unique.", start_id, stage="validation")
    if start_id in goals:
        return _failure(
            "Start node cannot also be a goal.", start_id, stage="validation"
        )
    missing = [goal for goal in goals if goal not in graph.nodes]
    if missing:
        return _failure(
            f"Goal node '{missing[0]}' was not found.",
            start_id,
            stage="validation",
        )

    costs = build_cost_matrix(graph, [start_id, *goals])
    if respect_goal_order:
        initial_order = [start_id, *goals]
        initial_cost = route_cost(initial_order, costs)
        optimized_order = list(initial_order)
        optimized_cost = initial_cost
        improvements = []
    else:
        initial_order = nearest_neighbor_order(start_id, goals, costs)
        if initial_order is None:
            return _failure(
                "Nearest Neighbor could not reach every selected goal.",
                start_id,
                stage="nearest_neighbor",
            )
        initial_cost = route_cost(initial_order, costs)
        optimized_order, optimized_cost, improvements = two_opt(
            initial_order,
            costs,
            max_iterations=max_two_opt_iterations,
        )

    if not math.isfinite(optimized_cost):
        unreachable_leg = next(
            (
                (source, target)
                for source, target in zip(optimized_order, optimized_order[1:])
                if not math.isfinite(costs.get((source, target), math.inf))
            ),
            None,
        )
        leg_text = (
            f" from '{unreachable_leg[0]}' to '{unreachable_leg[1]}'"
            if unreachable_leg
            else ""
        )
        return _failure(
            f"No road route exists{leg_text}.",
            start_id,
            stage="route_construction",
        )

    steps = [
        SearchStep(
            StepType.UPDATE,
            node_id=initial_order[1],
            metrics={
                "stage": "selected_order" if respect_goal_order else "nearest_neighbor",
                "route": " -> ".join(initial_order),
                "cost": initial_cost,
            },
        )
    ]
    for improvement in improvements:
        steps.append(
            SearchStep(
                StepType.UPDATE,
                node_id=improvement["route"][-1],
                metrics={
                    "stage": "2-opt",
                    "iteration": improvement["iteration"],
                    "reversed_segment": (
                        f"{improvement['left']}:{improvement['right']}"
                    ),
                    "previous_cost": improvement["previous_cost"],
                    "optimized_cost": improvement["optimized_cost"],
                    "route": " -> ".join(improvement["route"]),
                },
            )
        )

    full_path: list[str] = []
    actual_cost = 0.0
    leg_count = len(optimized_order) - 1
    for leg_index, (source, target) in enumerate(
        zip(optimized_order, optimized_order[1:]), start=1
    ):
        leg_cost, leg_path = _shortest_path(graph, source, target)
        if not leg_path or not math.isfinite(leg_cost):
            return _failure(
                f"No road path exists from '{source}' to '{target}'.",
                source,
                stage="route_construction",
                leg_index=leg_index,
            )
        full_path.extend(leg_path if not full_path else leg_path[1:])
        actual_cost += leg_cost

        for edge_from, edge_to in zip(leg_path, leg_path[1:]):
            steps.append(
                SearchStep(
                    StepType.DISCOVER,
                    node_id=edge_to,
                    edge_from=edge_from,
                    edge_to=edge_to,
                    metrics={
                        "stage": "route_leg",
                        "leg_index": leg_index,
                        "leg_count": leg_count,
                        "leg_start": source,
                        "leg_goal": target,
                    },
                )
            )
        steps.append(
            SearchStep(
                StepType.EXPAND,
                node_id=target,
                metrics={
                    "stage": "goal_reached",
                    "leg_index": leg_index,
                    "leg_count": leg_count,
                    "leg_cost": leg_cost,
                },
            )
        )

    steps.append(
        SearchStep(
            StepType.FINISH,
            node_id=optimized_order[-1],
            metrics={
                "success": True,
                "goals": len(goals),
                "nearest_neighbor_cost": initial_cost,
                "optimized_cost": actual_cost,
                "2opt_improvements": len(improvements),
                "route": " -> ".join(optimized_order),
            },
        )
    )

    if respect_goal_order:
        message = (
            f"Visited {len(goals)} goal(s) in the selected order; "
            f"route cost {actual_cost:.4f}."
        )
    else:
        message = (
            f"Nearest Neighbor + 2-Opt visited {len(goals)} goal(s), "
            f"improved cost from {initial_cost:.4f} to {actual_cost:.4f} "
            f"with {len(improvements)} accepted 2-Opt move(s)."
        )

    return SearchResult(
        path=full_path,
        steps=steps,
        total_cost=actual_cost,
        success=True,
        message=message,
        visited_order=list(full_path),
        goal_visit_order=optimized_order[1:],
    )


multi_location_nearest_neighbor_2opt = nearest_neighbor_2opt
