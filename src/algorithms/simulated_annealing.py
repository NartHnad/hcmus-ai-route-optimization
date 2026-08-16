# src.algorithms.simulated_annealing

"""Simulated Annealing route optimizer with first-class playback events.

The optimizer follows the AIMA-style SA transition rule, while exposing a
visualization protocol compatible with the project's GA playback:

* optimizer/logical events live under ``stage='sa_*'``;
* every visualized route starts with ``route_reset=True``;
* road geometry is replayed as DISCOVER/EXPAND events from a cached A* path
  matrix, so visualization never changes the objective function;
* ``goal_order`` travels with route frames so Map/Graph endpoint numbering can
  follow the currently displayed tour;
* the final SearchResult path is the best-so-far tour, not merely the last SA
  state.
"""

from __future__ import annotations

import math
import random
from typing import Iterable

from src.algorithms.a_star import a_star
from src.models.models import SearchResult, SearchStep, StepType

TEMPERATURE_EPSILON = 1e-2


def get_tour_cost(tour: list, distance_matrix: dict) -> float:
    """Return the total cached route cost for ``tour``."""
    total_cost = 0.0

    for from_node, to_node in zip(tour, tour[1:]):
        cost = distance_matrix.get((from_node, to_node), float("inf"))
        if not math.isfinite(cost):
            return float("inf")
        total_cost += cost

    return total_cost


def get_value(tour: list, distance_matrix: dict) -> float:
    """SA value: negative route distance, so a larger value is better."""
    distance = get_tour_cost(tour, distance_matrix)
    return -distance if math.isfinite(distance) else float("-inf")


def swap_two_locations(
    tour: list,
    respect_goal_order: bool = False,
    return_to_start: bool = False,
) -> list:
    """Create one neighboring tour by swapping two delivery locations."""
    next_tour = tour.copy()

    if respect_goal_order:
        return next_tour

    # START is fixed at index 0.  For a round trip, the final START is fixed too.
    start_idx = 1
    end_idx = len(next_tour) - 1 if return_to_start else len(next_tour)

    if end_idx - start_idx < 2:
        return next_tour

    i, j = random.sample(range(start_idx, end_idx), 2)
    next_tour[i], next_tour[j] = next_tour[j], next_tour[i]
    return next_tour


def exp_cooling_schedule(
    t: int,
    initial_temp: float = 500.0,
    decay_rate: float = 0.98,
) -> float:
    """Exponential cooling schedule used by the SA loop."""
    temperature = float(initial_temp) * (float(decay_rate) ** int(t))
    return temperature if temperature > TEMPERATURE_EPSILON else 0.0


def build_route_matrices(graph, locations: list) -> tuple[dict, dict]:
    """Pre-compute pairwise route costs and actual road-node paths with A*.

    SA evaluates many permutations, therefore A* is run once per ordered pair.
    The same cached path is used for objective evaluation and visualization.
    """
    distance_matrix = {}
    path_matrix = {}

    # ``return_to_start`` duplicates START at the end of ``locations``. Avoid
    # re-running identical pair searches while preserving dictionary semantics.
    unique_locations = list(dict.fromkeys(locations))

    for src in unique_locations:
        for dst in unique_locations:
            if src == dst:
                distance_matrix[(src, dst)] = 0.0
                path_matrix[(src, dst)] = [src]
                continue

            result = a_star(graph, src, dst)
            if result.success:
                distance_matrix[(src, dst)] = result.total_cost
                path_matrix[(src, dst)] = list(result.path)
            else:
                distance_matrix[(src, dst)] = float("inf")
                path_matrix[(src, dst)] = []

    return distance_matrix, path_matrix


def build_distance_matrix(graph, locations: list) -> dict:
    """Backward-compatible helper retained for existing callers/tests."""
    distance_matrix, _ = build_route_matrices(graph, locations)
    return distance_matrix


def _distance_from_value(value: float) -> float:
    return -value if math.isfinite(value) else float("inf")


def _goal_order(tour: Iterable[str], start: str, return_to_start: bool) -> list[str]:
    """Return only delivery nodes, in the order represented by ``tour``."""
    items = list(tour)
    if not items:
        return []

    order = items[1:]
    if return_to_start and order and order[-1] == start:
        order = order[:-1]
    return list(order)


def _construct_full_path(
    tour: list,
    path_matrix: dict,
) -> list[str]:
    """Concatenate cached point-to-point paths for a complete tour."""
    full_path: list[str] = []

    for source, target in zip(tour, tour[1:]):
        leg_path = path_matrix.get((source, target), [])
        if not leg_path:
            return []
        if not full_path:
            full_path.extend(leg_path)
        else:
            full_path.extend(leg_path[1:])

    return full_path


def _append_tour_visualization(
    steps: list,
    tour: list,
    path_matrix: dict,
    distance_matrix: dict,
    *,
    stage: str,
    route_frame: str,
    time_step: int,
    route_cost: float,
    route_role: str,
    start: str,
    return_to_start: bool,
    summary_metrics: dict | None = None,
) -> None:
    """Emit one complete, atomic route frame.

    The marker UPDATE mirrors the GA ``route_reset`` protocol.  MapWidget groups
    the marker and all road-edge events from the same ``route_frame`` into one JS
    render, preventing partial tours and cross-iteration batching.
    """
    summary = dict(summary_metrics or {})
    route_text = " -> ".join(tour)
    goal_order = _goal_order(tour, start, return_to_start)

    common = {
        "time_step": time_step,
        "route_frame": route_frame,
        "route_role": route_role,
        "route": route_text,
        "route_cost": (
            round(route_cost, 6) if math.isfinite(route_cost) else float("inf")
        ),
        "goal_order": goal_order,
        **summary,
    }
    compact_summary = {
        key: summary.get(key)
        for key in (
            "temperature",
            "candidate_distance",
            "current_distance",
            "best_distance",
            "delta_e",
            "acceptance_probability",
            "random_draw",
            "accepted",
            "decision",
            "is_new_best",
        )
        if key in summary
    }

    # Keep the same marker convention already used by GA: <stage>_route_start.
    # Example: stage='sa_iteration_route' -> 'sa_iteration_route_route_start'.
    steps.append(
        SearchStep(
            step_type=StepType.UPDATE,
            node_id=tour[0] if tour else None,
            metrics={
                **common,
                "stage": f"{stage}_route_start",
                "route_reset": True,
            },
        )
    )

    leg_count = max(0, len(tour) - 1)

    for leg_index, (source, target) in enumerate(zip(tour, tour[1:]), start=1):
        leg_path = path_matrix.get((source, target), [])
        leg_cost = distance_matrix.get((source, target), float("inf"))

        # Unreachable legs remain absent; never invent a direct map edge.
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
                        "time_step": time_step,
                        "route_frame": route_frame,
                        "route_role": route_role,
                        "route_cost": common["route_cost"],
                        **compact_summary,
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
                    "time_step": time_step,
                    "route_frame": route_frame,
                    "route_role": route_role,
                    "route_cost": common["route_cost"],
                    **compact_summary,
                    "leg_index": leg_index,
                    "leg_count": leg_count,
                    "leg_start": source,
                    "leg_goal": target,
                    "leg_cost": (
                        round(leg_cost, 6) if math.isfinite(leg_cost) else float("inf")
                    ),
                },
            )
        )


def _transition_decision(
    current_value: float,
    candidate_value: float,
    temperature: float,
) -> tuple[float, float, float | None, bool]:
    """Return ``delta_e, probability, random_draw, accepted`` robustly.

    Directed road graphs can make some permutations unreachable.  ``-inf - -inf``
    would otherwise become NaN and trap SA forever in the first infeasible tour.
    Treat two infeasible states as equal-value neighbors so SA can keep walking
    until it reaches a feasible permutation.
    """
    neg_inf = float("-inf")

    if current_value == neg_inf and candidate_value == neg_inf:
        delta_e = 0.0
    elif current_value == neg_inf:
        delta_e = float("inf")
    elif candidate_value == neg_inf:
        delta_e = float("-inf")
    else:
        delta_e = candidate_value - current_value

    if delta_e > 0:
        return delta_e, 1.0, None, True

    if delta_e == float("-inf"):
        probability = 0.0
    else:
        probability = math.exp(delta_e / temperature)

    random_draw = random.random()
    return delta_e, probability, random_draw, random_draw < probability


def simulated_annealing(
    graph,
    start,
    goals,
    respect_goal_order=False,
    return_to_start=False,
    initial_temp: float = 500.0,
    decay_rate: float = 0.98,
    log_every: int = 10,
    visualize_every: int = 10,
) -> SearchResult:
    """Optimize a multi-location tour with Simulated Annealing.

    ``visualize_every=1`` exposes one complete route frame per SA iteration.
    Raising it reduces UI workload without changing the optimization itself.
    ``log_every`` controls metric-only iteration events when an iteration is not
    being rendered as a route frame.
    """
    steps = []

    if isinstance(goals, str):
        goals = [item.strip() for item in goals.split(",") if item.strip()]
    else:
        goals = list(goals or [])

    locations = [start] + goals
    if return_to_start:
        locations.append(start)

    if len(locations) < 2:
        return SearchResult(
            path=[start],
            steps=[
                SearchStep(
                    step_type=StepType.FINISH,
                    node_id=start,
                    metrics={
                        "stage": "finish",
                        "success": True,
                        "total_cost": 0.0,
                        "sa_iterations": 0,
                        "goal_order": [],
                    },
                )
            ],
            total_cost=0.0,
            success=True,
            message="No delivery locations were provided.",
            visited_order=locations,
            goal_visit_order=[],
        )

    distance_matrix, path_matrix = build_route_matrices(graph, locations)

    # Respecting list order intentionally disables SA permutation search.  Still
    # emit the same route-frame protocol so playback remains consistent.
    if respect_goal_order:
        best_tour = locations.copy()
        best_value = get_value(best_tour, distance_matrix)
        best_distance = _distance_from_value(best_value)

        _append_tour_visualization(
            steps,
            best_tour,
            path_matrix,
            distance_matrix,
            stage="sa_final_route",
            route_frame="sa:preserved",
            time_step=0,
            route_cost=best_distance,
            route_role="preserved_order",
            start=start,
            return_to_start=return_to_start,
            summary_metrics={
                "temperature": 0.0,
                "best_distance": best_distance,
                "current_distance": best_distance,
                "accepted": True,
                "decision": "preserved_order",
                "is_new_best": True,
            },
        )
        iterations = 0
        message = (
            "Route constructed with preserved goal order; no SA optimization performed."
        )

    else:
        current = locations.copy()
        current_value = get_value(current, distance_matrix)
        best_tour = current.copy()
        best_value = current_value

        initial_distance = _distance_from_value(current_value)
        _append_tour_visualization(
            steps,
            current,
            path_matrix,
            distance_matrix,
            stage="sa_initial_route",
            route_frame="sa:initial",
            time_step=0,
            route_cost=initial_distance,
            route_role="initial_current",
            start=start,
            return_to_start=return_to_start,
            summary_metrics={
                "temperature": round(float(initial_temp), 6),
                "current_distance": initial_distance,
                "best_distance": initial_distance,
                "accepted": True,
                "decision": "initial",
                "is_new_best": True,
                "current_tour": " -> ".join(current),
                "best_tour": " -> ".join(best_tour),
            },
        )

        t = 1
        draw_every = max(1, int(visualize_every))
        metric_every = max(1, int(log_every))

        while True:
            temperature = exp_cooling_schedule(
                t,
                initial_temp=initial_temp,
                decay_rate=decay_rate,
            )
            if temperature == 0:
                break

            previous_state = current.copy()
            previous_value = current_value

            candidate = swap_two_locations(
                current,
                respect_goal_order=False,
                return_to_start=return_to_start,
            )
            candidate_value = get_value(candidate, distance_matrix)

            delta_e, acceptance_probability, random_draw, accepted = (
                _transition_decision(
                    current_value,
                    candidate_value,
                    temperature,
                )
            )

            if accepted:
                current = candidate
                current_value = candidate_value

            is_new_best = current_value > best_value
            if is_new_best:
                best_tour = current.copy()
                best_value = current_value

            previous_distance = _distance_from_value(previous_value)
            candidate_distance = _distance_from_value(candidate_value)
            current_distance = _distance_from_value(current_value)
            best_distance = _distance_from_value(best_value)

            iteration_metrics = {
                "stage": "sa_iteration",
                "time_step": t,
                "temperature": round(temperature, 6),
                "previous_distance": previous_distance,
                "candidate_distance": candidate_distance,
                "current_distance": current_distance,
                "best_distance": best_distance,
                "delta_e": (round(delta_e, 6) if math.isfinite(delta_e) else delta_e),
                "acceptance_probability": round(acceptance_probability, 6),
                "random_draw": (
                    round(random_draw, 6) if random_draw is not None else None
                ),
                "accepted": accepted,
                "decision": "accepted" if accepted else "rejected",
                "is_new_best": is_new_best,
                "previous_tour": " -> ".join(previous_state),
                "candidate_tour": " -> ".join(candidate),
                "current_tour": " -> ".join(current),
                "best_tour": " -> ".join(best_tour),
                "goal_order": _goal_order(current, start, return_to_start),
            }

            should_draw = t % draw_every == 0
            should_log = t % metric_every == 0

            if should_draw:
                # Draw the state that SA actually owns AFTER the accept/reject
                # decision.  Rejected candidates therefore leave the current tour
                # unchanged, matching the algorithm exactly.
                _append_tour_visualization(
                    steps,
                    current,
                    path_matrix,
                    distance_matrix,
                    stage="sa_iteration_route",
                    route_frame=f"sa:{t}",
                    time_step=t,
                    route_cost=current_distance,
                    route_role="current_after_iteration",
                    start=start,
                    return_to_start=return_to_start,
                    summary_metrics=iteration_metrics,
                )
            elif should_log:
                steps.append(
                    SearchStep(
                        step_type=StepType.UPDATE,
                        node_id=current[-1] if current else None,
                        metrics=iteration_metrics,
                    )
                )

            # Preserve a dedicated best event only when no route frame was emitted.
            # A rendered frame already contains ``is_new_best`` and best metrics.
            if is_new_best and not should_draw:
                steps.append(
                    SearchStep(
                        step_type=StepType.UPDATE,
                        node_id=best_tour[-1] if best_tour else None,
                        metrics={
                            "stage": "sa_best",
                            "time_step": t,
                            "temperature": round(temperature, 6),
                            "best_distance": best_distance,
                            "is_best": True,
                            "accepted": accepted,
                            "goal_order": _goal_order(
                                best_tour, start, return_to_start
                            ),
                            "tour": " -> ".join(best_tour),
                        },
                    )
                )

            t += 1

        iterations = t - 1
        message = f"Simulated Annealing completed after {iterations} time steps."
        best_distance = _distance_from_value(best_value)

        # Always end with a clean best-tour frame, even when visualize_every > 1.
        _append_tour_visualization(
            steps,
            best_tour,
            path_matrix,
            distance_matrix,
            stage="sa_final_route",
            route_frame="sa:final",
            time_step=iterations,
            route_cost=best_distance,
            route_role="final_best",
            start=start,
            return_to_start=return_to_start,
            summary_metrics={
                "temperature": 0.0,
                "current_distance": _distance_from_value(current_value),
                "best_distance": best_distance,
                "accepted": True,
                "decision": "final_best",
                "is_new_best": True,
                "best_tour": " -> ".join(best_tour),
            },
        )

    best_distance = _distance_from_value(best_value)
    full_path = _construct_full_path(best_tour, path_matrix)
    success = math.isfinite(best_distance) and bool(full_path)

    if not success:
        return SearchResult(
            path=[],
            steps=steps,
            total_cost=float("inf"),
            success=False,
            message="No feasible tour exists for the selected directed route orderings.",
            visited_order=best_tour,
            goal_visit_order=_goal_order(best_tour, start, return_to_start),
        )

    steps.append(
        SearchStep(
            step_type=StepType.FINISH,
            node_id=best_tour[-1],
            metrics={
                "stage": "finish",
                "success": True,
                "total_cost": round(best_distance, 6),
                "tour": " -> ".join(best_tour),
                "goal_order": _goal_order(best_tour, start, return_to_start),
                "sa_iterations": iterations,
                "step_count": len(steps) + 1,
            },
        )
    )

    return SearchResult(
        path=full_path,
        steps=steps,
        total_cost=best_distance,
        success=True,
        message=message,
        visited_order=best_tour,
        goal_visit_order=_goal_order(best_tour, start, return_to_start),
    )
