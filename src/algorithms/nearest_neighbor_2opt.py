# #NhatHuyChanged: production multi-location NN + 2-Opt optimizer with UI playback.
"""Multi-location routing with Nearest Neighbor followed by directed 2-Opt.

The optimizer works on a directed metric closure of the selected delivery
locations.  One multi-target Dijkstra run is performed per selected location so
both shortest-path costs and real road-node paths can be reused by the
optimization and by Map/Graph playback.

Visualization follows the same optimizer protocol used by GA and SA:

* logical optimizer events use ``stage='nn2opt_*'``;
* every displayed route frame starts with ``route_reset=True``;
* ``route_frame`` keeps one complete route atomic during autoplay;
* route edges are emitted as ``DISCOVER`` and reached goals as ``EXPAND``;
* ``goal_order`` keeps numbered endpoint markers synchronized with the route.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Mapping, Sequence
from typing import Iterable

from src.constants import StepType
from src.models.models import SearchResult, SearchStep


ALGORITHM_NAME = "Nearest Neighbor + 2-Opt"
_EPSILON = 1e-12


def _edge_cost(edge) -> float:
    """Return a finite, non-negative directed edge cost when possible."""
    cost = float(edge.calculate_cost())
    if not math.isfinite(cost) or cost < 0.0:
        return math.inf
    if cost > 0.0:
        return cost

    # Small hand-built test graphs may not have normalized composite costs yet.
    distance = float(getattr(edge, "distance", 0.0))
    return distance if math.isfinite(distance) and distance >= 0.0 else math.inf


def _normalize_goals(goal_ids) -> list[str]:
    if goal_ids is None:
        return []
    if isinstance(goal_ids, str):
        goal_ids = goal_ids.replace(";", ",").split(",")
    return [str(goal).strip() for goal in goal_ids if str(goal).strip()]


def _shortest_routes_from(
    graph,
    source: str,
    targets: Sequence[str],
) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Run one directed multi-target Dijkstra search from ``source``.

    Returns both exact costs and reconstructed road-node paths for all requested
    targets.  Unreachable targets receive ``math.inf`` and an empty path.
    """
    requested = set(targets)
    requested.discard(source)

    distances = {source: 0.0}
    parents: dict[str, str | None] = {source: None}
    frontier = [(0.0, source)]
    settled = set()
    found = set()

    while frontier and requested - found:
        current_cost, current = heapq.heappop(frontier)
        if current in settled or current_cost > distances.get(current, math.inf):
            continue
        settled.add(current)

        if current in requested:
            found.add(current)

        for edge in graph.get_neighbors(current):
            edge_cost = _edge_cost(edge)
            if not math.isfinite(edge_cost):
                continue

            candidate = current_cost + edge_cost
            neighbor = edge.to_node
            if candidate + _EPSILON < distances.get(neighbor, math.inf):
                distances[neighbor] = candidate
                parents[neighbor] = current
                heapq.heappush(frontier, (candidate, neighbor))

    costs: dict[str, float] = {}
    paths: dict[str, list[str]] = {}

    for target in targets:
        if target == source:
            costs[target] = 0.0
            paths[target] = [source]
            continue

        target_cost = distances.get(target, math.inf)
        costs[target] = target_cost
        if not math.isfinite(target_cost):
            paths[target] = []
            continue

        path = []
        cursor: str | None = target
        while cursor is not None:
            path.append(cursor)
            cursor = parents.get(cursor)
        path.reverse()
        paths[target] = path if path and path[0] == source else []

    return costs, paths


def _shortest_costs_from(graph, source: str, targets: Sequence[str]) -> dict[str, float]:
    """Compatibility wrapper returning only multi-target shortest-path costs."""
    costs, _ = _shortest_routes_from(graph, source, targets)
    return costs


def _shortest_path(graph, source: str, target: str) -> tuple[float, list[str]]:
    """Compatibility helper for tests and callers expecting a single path."""
    costs, paths = _shortest_routes_from(graph, source, [target])
    return costs.get(target, math.inf), paths.get(target, [])


def build_route_matrices(
    graph,
    locations: Sequence[str],
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], list[str]]]:
    """Build directed metric-closure costs and matching real road paths."""
    unique_locations = list(dict.fromkeys(locations))
    costs: dict[tuple[str, str], float] = {}
    paths: dict[tuple[str, str], list[str]] = {}

    for source in unique_locations:
        source_costs, source_paths = _shortest_routes_from(
            graph,
            source,
            unique_locations,
        )
        for target in unique_locations:
            costs[(source, target)] = source_costs.get(target, math.inf)
            paths[(source, target)] = list(source_paths.get(target, []))

    return costs, paths


def build_cost_matrix(graph, locations: Sequence[str]) -> dict[tuple[str, str], float]:
    """Backward-compatible directed metric-closure cost builder."""
    costs, _ = build_route_matrices(graph, locations)
    return costs


def route_cost(route: Sequence[str], costs: Mapping[tuple[str, str], float]) -> float:
    """Return the full directed cost of a route."""
    total = 0.0
    for source, target in zip(route, route[1:]):
        leg_cost = costs.get((source, target), math.inf)
        if not math.isfinite(leg_cost):
            return math.inf
        total += leg_cost
    return total


def _goal_order(route: Iterable[str], start_id: str, return_to_start: bool) -> list[str]:
    """Return only delivery goals, in the order represented by ``route``."""
    items = list(route)
    if not items:
        return []
    order = items[1:]
    if return_to_start and order and order[-1] == start_id:
        order = order[:-1]
    return list(order)


def nearest_neighbor_order(
    start_id: str,
    goal_ids: Sequence[str],
    costs: Mapping[tuple[str, str], float],
    *,
    return_to_start: bool = False,
    trace: list[dict] | None = None,
) -> list[str] | None:
    """Create a deterministic directed nearest-neighbor order.

    When building a round trip, the final remaining goal must also be able to
    reach Start.  This avoids constructing an obviously impossible closed tour.
    ``trace`` receives one accepted NN choice per step for UI playback.
    """
    remaining = list(goal_ids)
    input_rank = {goal: index for index, goal in enumerate(remaining)}
    order = [start_id]
    current = start_id
    accumulated_cost = 0.0

    while remaining:
        reachable = []
        for goal in remaining:
            leg_cost = costs.get((current, goal), math.inf)
            if not math.isfinite(leg_cost):
                continue
            if (
                return_to_start
                and len(remaining) == 1
                and not math.isfinite(costs.get((goal, start_id), math.inf))
            ):
                continue
            reachable.append(goal)

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
        leg_cost = costs[(current, next_goal)]
        accumulated_cost += leg_cost
        order.append(next_goal)
        remaining.remove(next_goal)

        if trace is not None:
            display_order = list(order[1:]) + list(remaining)
            trace.append(
                {
                    "iteration": len(order) - 1,
                    "from": current,
                    "selected_goal": next_goal,
                    "leg_cost": leg_cost,
                    "partial_cost": accumulated_cost,
                    "partial_route": list(order),
                    "remaining_goals": list(remaining),
                    "goal_order": display_order,
                }
            )

        current = next_goal

    if return_to_start:
        close_cost = costs.get((current, start_id), math.inf)
        if not math.isfinite(close_cost):
            return None
        order.append(start_id)
        if trace:
            trace[-1]["return_leg_cost"] = close_cost
            trace[-1]["closed_route_cost"] = accumulated_cost + close_cost
            trace[-1]["partial_route"] = list(order)
            trace[-1]["goal_order"] = list(order[1:-1])

    return order


def two_opt(
    route: Sequence[str],
    costs: Mapping[tuple[str, str], float],
    max_iterations: int = 100,
    *,
    return_to_start: bool = False,
) -> tuple[list[str], float, list[dict]]:
    """Improve a directed route while keeping fixed endpoints fixed.

    Candidate costs are recomputed in full instead of using the symmetric-TSP
    four-edge shortcut.  That remains correct on one-way road networks.  Start
    at index zero is always fixed; for round trips, the final Start is fixed too.
    Best-improvement selection makes accepted moves deterministic.
    """
    best = list(route)
    best_cost = route_cost(best, costs)
    improvements: list[dict] = []

    mutable_end = len(best) - 1 if return_to_start else len(best)
    if mutable_end - 1 < 2 or not math.isfinite(best_cost):
        return best, best_cost, improvements

    for iteration in range(1, max(0, int(max_iterations)) + 1):
        iteration_best = None

        for left in range(1, mutable_end - 1):
            for right in range(left + 1, mutable_end):
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
        previous_route = list(best)
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
                "previous_route": previous_route,
                "route": list(best),
            }
        )

    return best, best_cost, improvements


def _construct_full_path(
    route: Sequence[str],
    path_matrix: Mapping[tuple[str, str], Sequence[str]],
) -> list[str]:
    full_path: list[str] = []
    for source, target in zip(route, route[1:]):
        leg_path = list(path_matrix.get((source, target), []))
        if not leg_path:
            return []
        full_path.extend(leg_path if not full_path else leg_path[1:])
    return full_path


def _append_route_visualization(
    steps: list,
    route: Sequence[str],
    path_matrix: Mapping[tuple[str, str], Sequence[str]],
    costs: Mapping[tuple[str, str], float],
    *,
    stage: str,
    route_frame: str,
    route_role: str,
    start_id: str,
    return_to_start: bool,
    route_cost_value: float | None = None,
    summary_metrics: dict | None = None,
) -> None:
    """Emit one complete optimizer route frame using the GA/SA protocol."""
    route = list(route)
    if not route:
        return

    computed_cost = route_cost(route, costs)
    route_value = computed_cost if route_cost_value is None else route_cost_value
    summary = dict(summary_metrics or {})
    display_order = summary.pop(
        "goal_order",
        _goal_order(route, start_id, return_to_start),
    )

    common = {
        "route_frame": route_frame,
        "route_role": route_role,
        "route": " -> ".join(route),
        "route_cost": (
            round(route_value, 6) if math.isfinite(route_value) else float("inf")
        ),
        "goal_order": list(display_order),
        **summary,
    }

    # Match the existing GA/SA atomic-frame convention.  MapWidget strips the
    # trailing ``_route_start`` and then consumes events whose stage equals
    # ``stage`` and route_frame matches this marker.
    steps.append(
        SearchStep(
            step_type=StepType.UPDATE,
            node_id=route[0],
            metrics={
                **common,
                "stage": f"{stage}_route_start",
                "route_reset": True,
            },
        )
    )

    leg_count = max(0, len(route) - 1)
    for leg_index, (source, target) in enumerate(zip(route, route[1:]), start=1):
        leg_path = list(path_matrix.get((source, target), []))
        leg_cost = costs.get((source, target), math.inf)
        if not leg_path:
            continue

        for edge_index, (edge_from, edge_to) in enumerate(
            zip(leg_path, leg_path[1:]),
            start=1,
        ):
            steps.append(
                SearchStep(
                    step_type=StepType.DISCOVER,
                    node_id=edge_to,
                    edge_from=edge_from,
                    edge_to=edge_to,
                    metrics={
                        "stage": stage,
                        "route_frame": route_frame,
                        "route_role": route_role,
                        "route_cost": common["route_cost"],
                        "leg_index": leg_index,
                        "leg_count": leg_count,
                        "leg_start": source,
                        "leg_goal": target,
                        "leg_cost": (
                            round(leg_cost, 6)
                            if math.isfinite(leg_cost)
                            else float("inf")
                        ),
                        "edge_index": edge_index,
                    },
                )
            )

        steps.append(
            SearchStep(
                step_type=StepType.EXPAND,
                node_id=target,
                metrics={
                    "stage": stage,
                    "route_frame": route_frame,
                    "route_role": route_role,
                    "route_cost": common["route_cost"],
                    "leg_index": leg_index,
                    "leg_count": leg_count,
                    "leg_start": source,
                    "leg_goal": target,
                    "leg_cost": (
                        round(leg_cost, 6)
                        if math.isfinite(leg_cost)
                        else float("inf")
                    ),
                },
            )
        )


def _failure(message: str, node_id: str | None = None, **metrics) -> SearchResult:
    finish_metrics = {"stage": "nn2opt_finish", "success": False, **metrics}
    return SearchResult(
        path=[],
        steps=[
            SearchStep(
                step_type=StepType.FINISH,
                node_id=node_id,
                metrics=finish_metrics,
            )
        ],
        total_cost=0.0,
        success=False,
        message=message,
        visited_order=[],
        goal_visit_order=[],
    )


def nearest_neighbor_2opt(
    graph,
    start_id: str,
    goal_ids,
    respect_goal_order: bool = False,
    return_to_start: bool = False,
    max_two_opt_iterations: int = 100,
) -> SearchResult:
    """Visit all goals using NN initialization followed by directed 2-Opt."""
    goals = _normalize_goals(goal_ids)

    if graph is None or start_id not in getattr(graph, "nodes", {}):
        return _failure("Graph or start node is invalid.", stage="validation")
    if not goals:
        return _failure("At least one goal is required.", start_id, stage="validation")
    if len(set(goals)) != len(goals):
        return _failure("Goal nodes must be unique.", start_id, stage="validation")
    if start_id in goals:
        return _failure(
            "Start node cannot also be a goal.",
            start_id,
            stage="validation",
        )

    missing = [goal for goal in goals if goal not in graph.nodes]
    if missing:
        return _failure(
            f"Goal node '{missing[0]}' was not found.",
            start_id,
            stage="validation",
        )

    # The metric closure contains Start and each delivery goal exactly once.
    # Return-to-start uses the already-computed goal -> Start entries.
    costs, path_matrix = build_route_matrices(graph, [start_id, *goals])
    steps: list[SearchStep] = []

    if respect_goal_order:
        initial_order = [start_id, *goals]
        if return_to_start:
            initial_order.append(start_id)
        initial_cost = route_cost(initial_order, costs)
        if not math.isfinite(initial_cost):
            return _failure(
                "The selected goal order contains an unreachable road leg.",
                start_id,
                stage="nn2opt_preserved_order",
            )

        optimized_order = list(initial_order)
        optimized_cost = initial_cost
        improvements: list[dict] = []

        steps.append(
            SearchStep(
                step_type=StepType.UPDATE,
                node_id=optimized_order[-1],
                metrics={
                    "stage": "nn2opt_preserved_order",
                    "route": " -> ".join(optimized_order),
                    "route_cost": round(optimized_cost, 6),
                    "goal_order": list(goals),
                    "2opt_improvements": 0,
                },
            )
        )
        _append_route_visualization(
            steps,
            optimized_order,
            path_matrix,
            costs,
            stage="nn2opt_preserved_route",
            route_frame="nn2opt:preserved",
            route_role="preserved_order",
            start_id=start_id,
            return_to_start=return_to_start,
            route_cost_value=optimized_cost,
            summary_metrics={
                "iteration": 0,
                "nearest_neighbor_cost": optimized_cost,
                "optimized_cost": optimized_cost,
                "2opt_improvements": 0,
                "goal_order": list(goals),
            },
        )
    else:
        nn_trace: list[dict] = []
        initial_order = nearest_neighbor_order(
            start_id,
            goals,
            costs,
            return_to_start=return_to_start,
            trace=nn_trace,
        )
        if initial_order is None:
            return _failure(
                "Nearest Neighbor could not construct a feasible route through every selected goal.",
                start_id,
                stage="nn2opt_nearest_neighbor",
            )

        initial_cost = route_cost(initial_order, costs)
        if not math.isfinite(initial_cost):
            return _failure(
                "Nearest Neighbor produced a route containing an unreachable road leg.",
                start_id,
                stage="nn2opt_nearest_neighbor",
            )

        # Visualize NN construction after each accepted nearest-goal choice.
        for selection in nn_trace:
            iteration = int(selection["iteration"])
            partial_route = list(selection["partial_route"])
            partial_cost = route_cost(partial_route, costs)
            display_order = list(selection.get("goal_order") or [])

            steps.append(
                SearchStep(
                    step_type=StepType.UPDATE,
                    node_id=selection["selected_goal"],
                    metrics={
                        "stage": "nn2opt_nn_select",
                        "iteration": iteration,
                        "selected_goal": selection["selected_goal"],
                        "from_node": selection["from"],
                        "leg_cost": round(selection["leg_cost"], 6),
                        "partial_cost": round(partial_cost, 6),
                        "remaining_goals": list(selection["remaining_goals"]),
                        "route": " -> ".join(partial_route),
                        "goal_order": display_order,
                    },
                )
            )
            _append_route_visualization(
                steps,
                partial_route,
                path_matrix,
                costs,
                stage="nn2opt_nn_route",
                route_frame=f"nn2opt:nn:{iteration}",
                route_role=(
                    "nearest_neighbor_initial"
                    if iteration == len(goals)
                    else "nearest_neighbor_partial"
                ),
                start_id=start_id,
                return_to_start=(return_to_start and iteration == len(goals)),
                route_cost_value=partial_cost,
                summary_metrics={
                    "iteration": iteration,
                    "selected_goal": selection["selected_goal"],
                    "nearest_neighbor_cost": (
                        initial_cost if iteration == len(goals) else None
                    ),
                    "goal_order": display_order,
                },
            )

        steps.append(
            SearchStep(
                step_type=StepType.UPDATE,
                node_id=initial_order[-1],
                metrics={
                    "stage": "nn2opt_nn_complete",
                    "iteration": len(goals),
                    "nearest_neighbor_cost": round(initial_cost, 6),
                    "route_cost": round(initial_cost, 6),
                    "route": " -> ".join(initial_order),
                    "goal_order": _goal_order(
                        initial_order, start_id, return_to_start
                    ),
                },
            )
        )

        optimized_order, optimized_cost, improvements = two_opt(
            initial_order,
            costs,
            max_iterations=max_two_opt_iterations,
            return_to_start=return_to_start,
        )

        for improvement in improvements:
            iteration = int(improvement["iteration"])
            improved_route = list(improvement["route"])
            goal_order = _goal_order(improved_route, start_id, return_to_start)
            steps.append(
                SearchStep(
                    step_type=StepType.UPDATE,
                    node_id=(goal_order[-1] if goal_order else start_id),
                    metrics={
                        "stage": "nn2opt_2opt_iteration",
                        "iteration": iteration,
                        "reversed_segment": (
                            f"{improvement['left']}:{improvement['right']}"
                        ),
                        "previous_cost": round(improvement["previous_cost"], 6),
                        "optimized_cost": round(improvement["optimized_cost"], 6),
                        "nearest_neighbor_cost": round(initial_cost, 6),
                        "route": " -> ".join(improved_route),
                        "goal_order": goal_order,
                    },
                )
            )
            _append_route_visualization(
                steps,
                improved_route,
                path_matrix,
                costs,
                stage="nn2opt_2opt_route",
                route_frame=f"nn2opt:2opt:{iteration}",
                route_role="2opt_improvement",
                start_id=start_id,
                return_to_start=return_to_start,
                route_cost_value=improvement["optimized_cost"],
                summary_metrics={
                    "iteration": iteration,
                    "reversed_segment": (
                        f"{improvement['left']}:{improvement['right']}"
                    ),
                    "previous_cost": improvement["previous_cost"],
                    "optimized_cost": improvement["optimized_cost"],
                    "nearest_neighbor_cost": initial_cost,
                    "goal_order": goal_order,
                },
            )

    if not math.isfinite(optimized_cost):
        return _failure(
            "2-Opt could not produce a finite route on the directed road network.",
            start_id,
            stage="nn2opt_2opt",
        )

    full_path = _construct_full_path(optimized_order, path_matrix)
    if len(optimized_order) > 1 and not full_path:
        return _failure(
            "The optimized visit order contains a road leg that cannot be reconstructed.",
            start_id,
            stage="nn2opt_route_construction",
        )

    final_goal_order = _goal_order(optimized_order, start_id, return_to_start)

    # Always finish with a dedicated best/final route frame, even when 2-Opt made
    # no improvement.  This gives the UI one canonical route immediately before
    # FINISH highlights the result path in green.
    _append_route_visualization(
        steps,
        optimized_order,
        path_matrix,
        costs,
        stage="nn2opt_final_route",
        route_frame="nn2opt:final",
        route_role="final_optimized",
        start_id=start_id,
        return_to_start=return_to_start,
        route_cost_value=optimized_cost,
        summary_metrics={
            "iteration": len(improvements),
            "nearest_neighbor_cost": initial_cost,
            "optimized_cost": optimized_cost,
            "2opt_improvements": len(improvements),
            "goal_order": final_goal_order,
        },
    )

    steps.append(
        SearchStep(
            step_type=StepType.FINISH,
            node_id=optimized_order[-1],
            metrics={
                "stage": "nn2opt_finish",
                "success": True,
                "goals": len(goals),
                "nearest_neighbor_cost": round(initial_cost, 6),
                "optimized_cost": round(optimized_cost, 6),
                "2opt_improvements": len(improvements),
                "route": " -> ".join(optimized_order),
                "goal_order": final_goal_order,
                "return_to_start": bool(return_to_start),
            },
        )
    )

    if respect_goal_order:
        message = (
            f"Visited {len(goals)} goal(s) in the selected order; "
            f"route cost {optimized_cost:.4f}."
        )
    else:
        message = (
            f"Nearest Neighbor + 2-Opt visited {len(goals)} goal(s), "
            f"improved cost from {initial_cost:.4f} to {optimized_cost:.4f} "
            f"with {len(improvements)} accepted 2-Opt move(s)."
        )

    return SearchResult(
        path=full_path,
        steps=steps,
        total_cost=optimized_cost,
        success=True,
        message=message,
        visited_order=list(optimized_order),
        goal_visit_order=final_goal_order,
    )


multi_location_nearest_neighbor_2opt = nearest_neighbor_2opt
