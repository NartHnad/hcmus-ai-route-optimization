# src.algorithms.simulated_annealing

import math
import random

from src.algorithms.a_star import a_star
from src.models.models import SearchResult, SearchStep, StepType


def get_tour_cost(tour: list, distance_matrix: dict) -> float:
    """
    Calculate total Euclidean / Path distance for a given TSP tour order.
    """

    total_cost = 0.0

    for i in range(len(tour) - 1):
        from_node = tour[i]
        to_node = tour[i + 1]

        # Retrieve path cost between consecutive locations
        cost = distance_matrix.get((from_node, to_node), float("inf"))

        if cost == float("inf"):
            return float("inf")

        total_cost += cost

    return total_cost


def get_value(tour: list, distance_matrix: dict) -> float:
    """
    Value is defined as negative Distance.
    Higher value represents a better solution.
    """
    dist = get_tour_cost(tour, distance_matrix)

    if dist == float("inf"):
        return float("-inf")

    return -dist


def swap_two_locations(
    tour: list,
    respect_goal_order: bool = False,
    return_to_start: bool = False,
) -> list:
    next_tour = tour.copy()

    if respect_goal_order:
        return tour

    # No return:
    #   [START, G1, G2, G3]
    #    ^     ^^^^^^^^^^
    #    fixed   can swap
    #
    # Return:
    #   [START, G1, G2, G3, START]
    #    ^                    ^
    #    fixed              fixed
    start_idx = 1
    end_idx = len(next_tour) - 1 if return_to_start else len(next_tour)

    if end_idx - start_idx < 2:
        return next_tour

    # Randomly select two indices to swap
    i, j = random.sample(range(start_idx, end_idx), 2)

    # Swap the two locations
    next_tour[i], next_tour[j] = next_tour[j], next_tour[i]

    return next_tour


def exp_cooling_schedule(
    t: int, initial_temp: float = 1000.0, decay_rate: float = 0.995
) -> float:
    """
    Schedule mapping from time 't' to 'temperature' T.
    Returns 0 when temperature reaches below a negligible threshold.
    """
    T = float(initial_temp) * (float(decay_rate) ** int(t))

    return T if T > 1e-6 else 0.0


def build_route_matrices(graph, locations: list) -> tuple[dict, dict]:
    """
    Pre-compute pairwise distance AND the actual road-node path.

    SA evaluates thousands of tours.  Keeping the path matrix means visualization
    can replay every candidate tour without running A* again for every iteration.
    """
    distance_matrix = {}
    path_matrix = {}

    for src in locations:
        for dst in locations:
            if src == dst:
                distance_matrix[(src, dst)] = 0.0
                path_matrix[(src, dst)] = [src]
            else:
                res = a_star(graph, src, dst)
                if res.success:
                    distance_matrix[(src, dst)] = res.total_cost
                    path_matrix[(src, dst)] = list(res.path)
                else:
                    distance_matrix[(src, dst)] = float("inf")
                    path_matrix[(src, dst)] = []

    return distance_matrix, path_matrix


def build_distance_matrix(graph, locations: list) -> dict:
    """
    Pre-compute pairwise distances between cities using point-to-point pathfinder.
    """
    matrix = {}

    for src in locations:
        for dst in locations:
            if src == dst:
                matrix[(src, dst)] = 0.0

            else:
                res = a_star(graph, src, dst)

                matrix[(src, dst)] = res.total_cost if res.success else float("inf")

    return matrix


def _append_tour_draw_steps(
    steps: list,
    tour: list,
    path_matrix: dict,
    *,
    stage: str,
    time_step: int,
    accepted: bool | None = None,
    is_best: bool = False,
) -> None:
    """
    Convert one SA tour into normal DISCOVER/EXPAND events understood by the
    existing map playback renderer.

    UPDATE events are useful for text/log metrics, but the renderer draws graph
    exploration from DISCOVER/EXPAND.  Therefore every visualized SA iteration
    must expose the actual road edges of its candidate/current tour.
    """
    leg_count = max(0, len(tour) - 1)

    for leg_index, (source, target) in enumerate(zip(tour, tour[1:]), start=1):
        leg_path = path_matrix.get((source, target), [])

        # The distance matrix already treats this as unreachable.  Do not invent
        # a direct edge just for visualization.
        if not leg_path:
            continue

        for edge_from, edge_to in zip(leg_path, leg_path[1:]):
            steps.append(
                SearchStep(
                    step_type=StepType.DISCOVER,
                    node_id=edge_to,
                    edge_from=edge_from,
                    edge_to=edge_to,
                    metrics={
                        "stage": stage,
                        "time_step": time_step,
                        "leg_index": leg_index,
                        "leg_count": leg_count,
                        "leg_start": source,
                        "leg_goal": target,
                        "accepted": accepted,
                        "is_best": is_best,
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
                    "leg_index": leg_index,
                    "leg_count": leg_count,
                    "leg_start": source,
                    "leg_goal": target,
                    "accepted": accepted,
                    "is_best": is_best,
                },
            )
        )


def simulated_annealing(
    graph,
    start,
    goals,
    respect_goal_order=False,
    return_to_start=False,
    initial_temp: float = 1000.0,
    decay_rate: float = 0.995,
    log_every=1,
    visualize_every: int = 1,
) -> SearchResult:
    """
    Simulated Annealing algorithm strictly matching the AIMA textbook pseudocode.

    Pseudocode structure:
        current = Make-Node(problem.Initial-State)
        for t = 1 to infinity do
            T = schedule(t)
            if T == 0 then return current
            next = a randomly selected successor of current
            DeltaE = next.Value - current.Value
            if DeltaE > 0 then current = next
            else current = next only with probability exp(DeltaE / T)
    """

    steps = []

    # Normalize goals
    if isinstance(goals, str):
        if "," in goals:
            goals = [loc.strip() for loc in goals.split(",")]
        else:
            goals = [goals]
    else:
        goals = list(goals or [])

    # Start must always be the first location
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
                        "total_cost": 0.0,
                        "tour": start,
                    },
                )
            ],
            total_cost=0.0,
            success=True,
            message="No delivery locations were provided.",
            visited_order=locations,
        )

    # 1. Pre-calculate distance matrix
    dist_matrix, path_matrix = build_route_matrices(graph, locations)
    # =========================================================
    # CASE 1: Goal order must be preserved --> Khong han la SA nua do co dinh goal
    # =========================================================
    if respect_goal_order:
        best_tour = locations.copy()
        best_val = get_value(best_tour, dist_matrix)

        message = (
            "Route constructed with preserved goal order; no SA optimization performed"
        )

        if best_val != float("-inf"):
            steps.append(
                SearchStep(
                    step_type=StepType.UPDATE,
                    node_id=(best_tour[1] if len(best_tour) > 1 else best_tour[0]),
                    metrics={
                        "time_step": 0,
                        "temperature": 0,
                        "best_distance": round(-best_val, 2),
                        "tour": " -> ".join(best_tour),
                    },
                )
            )

    # =========================================================
    # CASE 2: Goal order can be optimized
    # =========================================================
    else:

        current = locations.copy()
        current_val = get_value(current, dist_matrix)

        best_tour = current.copy()
        best_val = current_val

        # Emit the initial SA state so the UI can start playback before t = 1.
        steps.append(
            SearchStep(
                step_type=StepType.UPDATE,
                node_id=current[0] if current else None,
                metrics={
                    "stage": "sa_initial",
                    "time_step": 0,
                    "temperature": round(float(initial_temp), 2),
                    "current_distance": round(-current_val, 2),
                    "best_distance": round(-best_val, 2),
                    "current_tour": " -> ".join(current),
                    "best_tour": " -> ".join(best_tour),
                },
            )
        )

        # Draw the initial tour immediately.  Without DISCOVER/EXPAND events the
        # UI only logs the UPDATE and the map appears frozen.
        _append_tour_draw_steps(
            steps,
            current,
            path_matrix,
            stage="sa_initial_route",
            time_step=0,
            accepted=True,
            is_best=True,
        )

        t = 1

        # 3. for t = 1 to infinity do
        while True:

            # T = schedule(t)
            T = exp_cooling_schedule(
                t, initial_temp=initial_temp, decay_rate=decay_rate
            )

            # if T == 0 then return current
            if T == 0:
                break

            # next = a randomly selected successor of current (Swap two cities)
            next_state = swap_two_locations(
                current,
                respect_goal_order=respect_goal_order,
                return_to_start=return_to_start,
            )
            next_val = get_value(next_state, dist_matrix)

            # Difference in value
            # DeltaE = next.Value - current.Value
            delta_e = next_val - current_val

            # Keep the previous state for a complete per-iteration trace.
            previous_state = current.copy()
            previous_val = current_val

            # Accept logic
            accepted = False
            acceptance_probability = 1.0 if delta_e > 0 else math.exp(delta_e / T)
            random_draw = None

            if delta_e > 0:
                current = next_state
                current_val = next_val
                accepted = True

            else:
                # current = next only with probability exp(DeltaE / T)
                random_draw = random.random()

                if random_draw < acceptance_probability:
                    current = next_state
                    current_val = next_val
                    accepted = True

            # Track global optimum before emitting the iteration so every
            # sa_iteration step contains the up-to-date best state.
            is_new_best = current_val > best_val
            if is_new_best:
                best_tour = current.copy()
                best_val = current_val

            # LOG SA EXPLORATION
            steps.append(
                SearchStep(
                    step_type=StepType.UPDATE,
                    node_id=current[-1] if current else None,
                    metrics={
                        "stage": "sa_iteration",
                        "time_step": t,
                        "temperature": round(T, 2),
                        "previous_distance": round(-previous_val, 2),
                        "candidate_distance": round(-next_val, 2),
                        "current_distance": round(-current_val, 2),
                        "best_distance": round(-best_val, 2),
                        "delta_e": round(delta_e, 6),
                        "acceptance_probability": round(acceptance_probability, 6),
                        "random_draw": (
                            round(random_draw, 6) if random_draw is not None else None
                        ),
                        "accepted": accepted,
                        "decision": "accepted" if accepted else "rejected",
                        "is_new_best": is_new_best,
                        "previous_tour": " -> ".join(previous_state),
                        "candidate_tour": " -> ".join(next_state),
                        "current_tour": " -> ".join(current),
                        "best_tour": " -> ".join(best_tour),
                    },
                )
            )

            # IMPORTANT: UPDATE alone does not draw on the map.  
            # Replay the candidate's real road edges using DISCOVER/EXPAND, exactly like
            # graph-search visualization.
            draw_every = max(1, int(visualize_every))
            if t % draw_every == 0:
                _append_tour_draw_steps(
                    steps,
                    next_state,
                    path_matrix,
                    stage="sa_candidate_route",
                    time_step=t,
                    accepted=accepted,
                    is_best=is_new_best,
                )


            if is_new_best:
                # Keep a dedicated event for renderers that highlight best-so-far.
                steps.append(
                    SearchStep(
                        step_type=StepType.UPDATE,
                        node_id=best_tour[-1],
                        metrics={
                            "stage": "sa_best",
                            "is_best": True,
                            "time_step": t,
                            "temperature": round(T, 2),
                            "accepted": accepted,
                            "best_distance": round(-best_val, 2),
                            "tour": " -> ".join(best_tour),
                        },
                    )
                )

            t += 1

        message = f"Simulated Annealing completed after {t - 1} time steps."

    # =========================================================
    # Construct actual graph path
    # =========================================================
    # 4. Construct turn-by-turn road path from best tour
    best_distance = -best_val
    full_path = []

    leg_count = len(best_tour) - 1

    for leg_index, (source, target) in enumerate(
        zip(best_tour, best_tour[1:]),
        start=1,
    ):
        sub_res = a_star(graph, source, target)

        if not sub_res.success:
            return SearchResult(
                path=[],
                steps=steps,
                total_cost=float("inf"),
                success=False,
                message=f"No path from {source} to {target}.",
                visited_order=best_tour,
            )

        leg_path = sub_res.path

        if not full_path:
            full_path.extend(leg_path)
        else:
            full_path.extend(leg_path[1:])

        # Emit actual road edges for UI playback
        for edge_from, edge_to in zip(leg_path, leg_path[1:]):
            steps.append(
                SearchStep(
                    step_type=StepType.DISCOVER,
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
                step_type=StepType.EXPAND,
                node_id=target,
                metrics={
                    "stage": "goal_reached",
                    "leg_index": leg_index,
                    "leg_count": leg_count,
                    "leg_start": source,
                    "leg_goal": target,
                    "leg_cost": round(sub_res.total_cost, 2),
                },
            )
        )

    # =========================================================
    # Finish step
    # =========================================================

    steps.append(
        SearchStep(
            step_type=StepType.FINISH,
            node_id=best_tour[-1],
            metrics={
                "stage": "finish",
                "success": True,
                "total_cost": round(best_distance, 2),
                "tour": " -> ".join(best_tour),
                "sa_iterations": (t - 1) if not respect_goal_order else 0,
                "step_count": len(steps) + 1,
            },
        )
    )

    return SearchResult(
        path=full_path,
        steps=steps,
        total_cost=best_distance,
        success=True if best_distance < float("inf") else False,
        message=message,
        visited_order=best_tour,
        goal_visit_order=(
            best_tour[1:-1] if return_to_start and len(best_tour) > 1 else best_tour[1:]
        ),
    )
