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

    return T if T > 1e-4 else 0.0


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


def simulated_annealing(
    graph,
    start,
    goals,
    respect_goal_order=False,
    return_to_start=False,
    initial_temp: float = 1000.0,
    decay_rate: float = 0.995,
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
    dist_matrix = build_distance_matrix(graph, locations)

    # =========================================================
    # CASE 1: Goal order must be preserved --> Khong han la SA nua do co dinh goal
    # =========================================================
    if respect_goal_order:
        best_tour = locations.copy()
        best_val = get_value(best_tour, dist_matrix)

        message = "Route constructed with preserved goal order."

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

            # Accept logic from pseudocode
            if delta_e > 0:
                current = next_state
                current_val = next_val

            else:
                # current = next only with probability exp(DeltaE / T)
                prob = math.exp(delta_e / T)
                if random.random() < prob:
                    current = next_state
                    current_val = next_val

            # Track global optimum
            if current_val > best_val:
                best_tour = current.copy()
                best_val = current_val

                # Emit GUI update step event
                steps.append(
                    SearchStep(
                        step_type=StepType.UPDATE,
                        node_id=best_tour[1] if len(best_tour) > 1 else locations[0],
                        metrics={
                            "time_step": t,
                            "temperature": round(T, 2),
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

    for i in range(len(best_tour) - 1):
        sub_res = a_star(graph, best_tour[i], best_tour[i + 1])
        if sub_res.success:
            if not full_path:
                full_path.extend(sub_res.path)
            else:
                full_path.extend(sub_res.path[1:])

    # =========================================================
    # Finish step
    # =========================================================

    steps.append(
        SearchStep(
            step_type=StepType.FINISH,
            node_id=best_tour[-1],
            metrics={
                "total_cost": round(best_distance, 2),
                "tour": " -> ".join(best_tour),
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
    )
