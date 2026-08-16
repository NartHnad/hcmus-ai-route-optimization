# src.algorithms.genetic_algorithm

from __future__ import annotations

import math
import random
from typing import Sequence

from src.algorithms.a_star import a_star
from src.models.models import SearchResult, SearchStep, StepType


ALGORITHM_NAME = "Genetic Algorithm (GA)"
_EPSILON = 1e-12


def _normalize_goals(goals) -> list[str]:
    if goals is None:
        return []
    if isinstance(goals, str):
        goals = goals.replace(";", ",").split(",")
    return [str(goal).strip() for goal in goals if str(goal).strip()]


def _failure(message: str, node_id: str | None = None, **metrics) -> SearchResult:
    return SearchResult(
        path=[],
        steps=[
            SearchStep(
                step_type=StepType.FINISH,
                node_id=node_id,
                metrics={"success": False, **metrics},
            )
        ],
        total_cost=0.0,
        success=False,
        message=message,
    )


def _tour_from_chromosome(
    start: str,
    chromosome: Sequence[str],
    return_to_start: bool,
) -> list[str]:
    tour = [start, *chromosome]
    if return_to_start:
        tour.append(start)
    return tour


def _tour_text(tour: Sequence[str]) -> str:
    return " -> ".join(map(str, tour))


def build_pairwise_cache(
    graph,
    locations: Sequence[str],
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], list[str]]]:
    """Precompute shortest-path costs and exact road paths between selected locations.

    GA works on permutations of delivery locations, while the renderer needs real road
    edges. Caching both cost and path lets every generation be visualized without
    rerunning A* thousands of times.
    """

    unique_locations = list(dict.fromkeys(locations))
    costs: dict[tuple[str, str], float] = {}
    paths: dict[tuple[str, str], list[str]] = {}

    for src in unique_locations:
        for dst in unique_locations:
            if src == dst:
                costs[(src, dst)] = 0.0
                paths[(src, dst)] = [src]
                continue

            result = a_star(graph, src, dst)
            if result.success and result.path and math.isfinite(result.total_cost):
                costs[(src, dst)] = float(result.total_cost)
                paths[(src, dst)] = list(result.path)
            else:
                costs[(src, dst)] = math.inf
                paths[(src, dst)] = []

    return costs, paths


def get_tour_cost(
    tour: Sequence[str],
    distance_matrix: dict[tuple[str, str], float],
) -> float:
    total = 0.0
    for src, dst in zip(tour, tour[1:]):
        leg_cost = distance_matrix.get((src, dst), math.inf)
        if not math.isfinite(leg_cost):
            return math.inf
        total += leg_cost
    return total


def get_fitness(cost: float) -> float:
    """Convert a route cost to a maximization fitness value for display/analysis."""
    if not math.isfinite(cost):
        return 0.0
    return 1.0 / (1.0 + max(0.0, cost))


def _evaluate_population(
    population: Sequence[Sequence[str]],
    start: str,
    return_to_start: bool,
    distance_matrix: dict[tuple[str, str], float],
) -> list[tuple[float, tuple[str, ...], list[str]]]:
    evaluated = []
    for chromosome in population:
        route = _tour_from_chromosome(start, chromosome, return_to_start)
        cost = get_tour_cost(route, distance_matrix)
        evaluated.append((cost, tuple(map(str, chromosome)), list(chromosome)))

    # Stable deterministic tie-break by chromosome text.
    evaluated.sort(key=lambda item: (item[0], item[1]))
    return evaluated


def _nearest_neighbor_seed(
    start: str,
    goals: Sequence[str],
    distance_matrix: dict[tuple[str, str], float],
) -> list[str] | None:
    remaining = list(goals)
    rank = {goal: i for i, goal in enumerate(remaining)}
    chromosome: list[str] = []
    current = start

    while remaining:
        reachable = [
            goal
            for goal in remaining
            if math.isfinite(distance_matrix.get((current, goal), math.inf))
        ]
        if not reachable:
            return None

        nxt = min(
            reachable,
            key=lambda goal: (
                distance_matrix[(current, goal)],
                rank[goal],
                str(goal),
            ),
        )
        chromosome.append(nxt)
        remaining.remove(nxt)
        current = nxt

    return chromosome


def _initial_population(
    goals: Sequence[str],
    population_size: int,
    rng: random.Random,
    start: str,
    distance_matrix: dict[tuple[str, str], float],
) -> list[list[str]]:
    """Create a diverse permutation population with a few useful deterministic seeds."""

    base = list(goals)
    population: list[list[str]] = []

    def add(chromosome: Sequence[str] | None) -> None:
        if chromosome is None:
            return
        candidate = list(chromosome)
        if candidate not in population:
            population.append(candidate)

    add(base)
    add(list(reversed(base)))
    add(_nearest_neighbor_seed(start, base, distance_matrix))

    attempts = 0
    max_unique_attempts = max(100, population_size * 20)
    while len(population) < population_size and attempts < max_unique_attempts:
        candidate = base.copy()
        rng.shuffle(candidate)
        add(candidate)
        attempts += 1

    # If n! is smaller than population_size, duplicates are valid GA individuals.
    while len(population) < population_size:
        candidate = base.copy()
        rng.shuffle(candidate)
        population.append(candidate)

    return population[:population_size]


def tournament_selection(
    evaluated_population: Sequence[tuple[float, tuple[str, ...], list[str]]],
    rng: random.Random,
    tournament_size: int = 3,
) -> tuple[list[str], float]:
    """Select one parent; lower route cost wins the tournament."""

    if not evaluated_population:
        return [], math.inf

    k = min(max(1, int(tournament_size)), len(evaluated_population))
    contenders = rng.sample(list(evaluated_population), k)
    winner = min(contenders, key=lambda item: (item[0], item[1]))
    return list(winner[2]), float(winner[0])


def order_crossover(
    parent1: Sequence[str],
    parent2: Sequence[str],
    rng: random.Random,
) -> tuple[list[str], tuple[int, int] | None]:
    """Order Crossover (OX) for permutation chromosomes.

    A contiguous segment is copied from parent1. The remaining positions are filled
    in parent2 order, skipping genes already present in the copied segment.
    """

    n = len(parent1)
    if n < 2:
        return list(parent1), None

    left, right = sorted(rng.sample(range(n), 2))
    child: list[str | None] = [None] * n
    child[left : right + 1] = parent1[left : right + 1]

    used = set(parent1[left : right + 1])
    fill_genes = [
        parent2[index % n]
        for index in range(right + 1, right + 1 + n)
        if parent2[index % n] not in used
    ]
    fill_positions = [
        index % n
        for index in range(right + 1, right + 1 + n)
        if child[index % n] is None
    ]

    for position, gene in zip(fill_positions, fill_genes):
        child[position] = gene

    return [gene for gene in child if gene is not None], (left, right)


def swap_mutation(
    chromosome: Sequence[str],
    rng: random.Random,
    mutation_rate: float,
) -> tuple[list[str], tuple[int, int] | None]:
    mutated = list(chromosome)
    if len(mutated) < 2 or rng.random() >= mutation_rate:
        return mutated, None

    i, j = sorted(rng.sample(range(len(mutated)), 2))
    mutated[i], mutated[j] = mutated[j], mutated[i]
    return mutated, (i, j)


def _append_route_visualization(
    steps: list[SearchStep],
    tour: Sequence[str],
    path_cache: dict[tuple[str, str], list[str]],
    distance_matrix: dict[tuple[str, str], float],
    *,
    stage: str,
    generation: int,
    route_cost: float,
    is_global_best: bool,
) -> None:
    """Emit real road-edge events so the existing playback can draw the GA route."""

    leg_count = max(0, len(tour) - 1)

    # Marker event tells a GA-aware renderer that the next DISCOVER events are a new
    # complete route snapshot. Existing renderers can safely ignore this UPDATE.
    steps.append(
        SearchStep(
            step_type=StepType.UPDATE,
            node_id=tour[0] if tour else None,
            metrics={
                "stage": f"{stage}_route_start",
                "generation": generation,
                "route": _tour_text(tour),
                "route_cost": round(route_cost, 6),
                "is_global_best": is_global_best,
                "route_reset": True,
            },
        )
    )

    for leg_index, (source, target) in enumerate(zip(tour, tour[1:]), start=1):
        leg_path = path_cache.get((source, target), [])
        leg_cost = distance_matrix.get((source, target), math.inf)

        for edge_index, (edge_from, edge_to) in enumerate(
            zip(leg_path, leg_path[1:]), start=1
        ):
            steps.append(
                SearchStep(
                    step_type=StepType.DISCOVER,
                    node_id=edge_to,
                    edge_from=edge_from,
                    edge_to=edge_to,
                    metrics={
                        "stage": stage,
                        "generation": generation,
                        "route_cost": round(route_cost, 6),
                        "is_global_best": is_global_best,
                        "leg_index": leg_index,
                        "leg_count": leg_count,
                        "leg_start": source,
                        "leg_goal": target,
                        "leg_cost": round(leg_cost, 6)
                        if math.isfinite(leg_cost)
                        else math.inf,
                        "edge_index": edge_index,
                        "route_reset": False,
                    },
                )
            )

        steps.append(
            SearchStep(
                step_type=StepType.EXPAND,
                node_id=target,
                metrics={
                    "stage": stage,
                    "generation": generation,
                    "route_cost": round(route_cost, 6),
                    "is_global_best": is_global_best,
                    "leg_index": leg_index,
                    "leg_count": leg_count,
                    "leg_start": source,
                    "leg_goal": target,
                    "leg_cost": round(leg_cost, 6)
                    if math.isfinite(leg_cost)
                    else math.inf,
                },
            )
        )


def _construct_full_path(
    tour: Sequence[str],
    path_cache: dict[tuple[str, str], list[str]],
) -> list[str]:
    full_path: list[str] = []

    for source, target in zip(tour, tour[1:]):
        leg_path = path_cache.get((source, target), [])
        if not leg_path:
            return []
        full_path.extend(leg_path if not full_path else leg_path[1:])

    return full_path or (list(tour[:1]) if tour else [])


def genetic_algorithm(
    graph,
    start,
    goals,
    respect_goal_order: bool = False,
    return_to_start: bool = False,
    population_size: int = 30,
    generations: int = 100,
    crossover_rate: float = 0.90,
    mutation_rate: float = 0.10,
    elitism: int = 2,
    tournament_size: int = 3,
    random_seed: int | None = None,
    visualize_every: int = 1,
    emit_operator_steps: bool = True,
) -> SearchResult:
    """Optimize a multi-location route with a permutation Genetic Algorithm.

    Representation
    --------------
    A chromosome contains only delivery goals. The start node is fixed and, when
    ``return_to_start`` is true, the start node is appended again during evaluation.

    Operators
    ---------
    * Selection: tournament selection
    * Crossover: Order Crossover (OX), valid for permutations
    * Mutation: swap mutation
    * Replacement: generational replacement with elitism

    SearchStep / playback
    ---------------------
    GA logic is emitted as UPDATE events (initial population, selection, crossover,
    mutation, generation summaries and best-so-far). The best route of every
    ``visualize_every`` generation is expanded into real A* road edges using
    DISCOVER and goal arrivals using EXPAND so the current map playback can draw it.
    """

    goals = _normalize_goals(goals)
    start = str(start)

    # ----------------------------- Validation -----------------------------
    if graph is None or start not in getattr(graph, "nodes", {}):
        return _failure("Graph or start node is invalid.", start, stage="validation")
    if not goals:
        return _failure("At least one goal is required.", start, stage="validation")
    if len(set(goals)) != len(goals):
        return _failure("Goal nodes must be unique.", start, stage="validation")
    if start in goals:
        return _failure(
            "Start node cannot also be a goal.", start, stage="validation"
        )

    missing = [goal for goal in goals if goal not in graph.nodes]
    if missing:
        return _failure(
            f"Goal node '{missing[0]}' was not found.",
            start,
            stage="validation",
        )

    population_size = max(2, int(population_size))
    generations = max(0, int(generations))
    crossover_rate = min(1.0, max(0.0, float(crossover_rate)))
    mutation_rate = min(1.0, max(0.0, float(mutation_rate)))
    elitism = min(max(0, int(elitism)), population_size)
    tournament_size = min(max(1, int(tournament_size)), population_size)
    visualize_every = max(1, int(visualize_every))
    rng = random.Random(random_seed)

    steps: list[SearchStep] = []

    # ----------------------- Pairwise A* precomputation -------------------
    distance_matrix, path_cache = build_pairwise_cache(graph, [start, *goals])

    steps.append(
        SearchStep(
            step_type=StepType.UPDATE,
            node_id=start,
            metrics={
                "stage": "ga_precompute",
                "locations": len(goals) + 1,
                "pairwise_entries": len(distance_matrix),
                "return_to_start": return_to_start,
            },
        )
    )

    # ----------------------- Fixed-order compatibility ---------------------
    if respect_goal_order:
        best_tour = _tour_from_chromosome(start, goals, return_to_start)
        best_cost = get_tour_cost(best_tour, distance_matrix)
        if not math.isfinite(best_cost):
            return _failure(
                "No valid road route exists for the selected goal order.",
                start,
                stage="route_construction",
            )

        steps.append(
            SearchStep(
                step_type=StepType.UPDATE,
                node_id=goals[0],
                metrics={
                    "stage": "ga_fixed_order",
                    "generation": 0,
                    "route": _tour_text(best_tour),
                    "cost": round(best_cost, 6),
                    "optimization_skipped": True,
                },
            )
        )
        _append_route_visualization(
            steps,
            best_tour,
            path_cache,
            distance_matrix,
            stage="ga_final_route",
            generation=0,
            route_cost=best_cost,
            is_global_best=True,
        )

        full_path = _construct_full_path(best_tour, path_cache)
        steps.append(
            SearchStep(
                step_type=StepType.FINISH,
                node_id=best_tour[-1],
                metrics={
                    "stage": "finish",
                    "success": True,
                    "algorithm": ALGORITHM_NAME,
                    "generations": 0,
                    "total_cost": round(best_cost, 6),
                    "tour": _tour_text(best_tour),
                    "step_count": len(steps) + 1,
                },
            )
        )
        return SearchResult(
            path=full_path,
            steps=steps,
            total_cost=best_cost,
            success=True,
            message=(
                "Route constructed with preserved goal order; "
                "GA optimization was skipped."
            ),
            visited_order=best_tour,
            goal_visit_order=list(goals),
        )

    # --------------------------- Generation 0 ------------------------------
    population = _initial_population(
        goals,
        population_size,
        rng,
        start,
        distance_matrix,
    )
    evaluated = _evaluate_population(
        population,
        start,
        return_to_start,
        distance_matrix,
    )

    finite_count = sum(math.isfinite(item[0]) for item in evaluated)
    if finite_count == 0:
        return _failure(
            "GA could not construct any finite route through all selected goals.",
            start,
            stage="initial_population",
        )

    generation_best_cost, _, generation_best_chromosome = evaluated[0]
    global_best_chromosome = list(generation_best_chromosome)
    global_best_cost = float(generation_best_cost)
    global_best_generation = 0
    generation_best_tour = _tour_from_chromosome(
        start, generation_best_chromosome, return_to_start
    )

    steps.append(
        SearchStep(
            step_type=StepType.UPDATE,
            node_id=generation_best_tour[-1],
            metrics={
                "stage": "ga_initial_population",
                "generation": 0,
                "population_size": len(population),
                "finite_individuals": finite_count,
                "best_cost": round(generation_best_cost, 6),
                "best_fitness": round(get_fitness(generation_best_cost), 12),
                "best_tour": _tour_text(generation_best_tour),
                "random_seed": random_seed,
            },
        )
    )

    _append_route_visualization(
        steps,
        generation_best_tour,
        path_cache,
        distance_matrix,
        stage="ga_generation_route",
        generation=0,
        route_cost=generation_best_cost,
        is_global_best=True,
    )

    # --------------------------- Evolution loop ----------------------------
    completed_generations = 0

    for generation in range(1, generations + 1):
        previous_evaluated = evaluated
        elite_count = min(elitism, len(previous_evaluated))
        next_population = [
            list(previous_evaluated[index][2]) for index in range(elite_count)
        ]

        if emit_operator_steps:
            elite_tours = [
                _tour_text(
                    _tour_from_chromosome(
                        start,
                        previous_evaluated[index][2],
                        return_to_start,
                    )
                )
                for index in range(elite_count)
            ]
            steps.append(
                SearchStep(
                    step_type=StepType.UPDATE,
                    node_id=(next_population[0][-1] if next_population else start),
                    metrics={
                        "stage": "ga_elitism",
                        "generation": generation,
                        "elite_count": elite_count,
                        "elite_tours": elite_tours,
                    },
                )
            )

        mating_index = 0
        while len(next_population) < population_size:
            mating_index += 1

            parent1, parent1_cost = tournament_selection(
                previous_evaluated, rng, tournament_size
            )
            parent2, parent2_cost = tournament_selection(
                previous_evaluated, rng, tournament_size
            )

            if emit_operator_steps:
                steps.append(
                    SearchStep(
                        step_type=StepType.UPDATE,
                        node_id=parent1[-1] if parent1 else start,
                        metrics={
                            "stage": "ga_selection",
                            "generation": generation,
                            "mating_index": mating_index,
                            "selection": "tournament",
                            "tournament_size": tournament_size,
                            "parent1_cost": round(parent1_cost, 6),
                            "parent2_cost": round(parent2_cost, 6),
                            "parent1": _tour_text(
                                _tour_from_chromosome(
                                    start, parent1, return_to_start
                                )
                            ),
                            "parent2": _tour_text(
                                _tour_from_chromosome(
                                    start, parent2, return_to_start
                                )
                            ),
                        },
                    )
                )

            crossover_draw = rng.random()
            did_crossover = len(goals) >= 2 and crossover_draw < crossover_rate

            if did_crossover:
                child1, cuts1 = order_crossover(parent1, parent2, rng)
                # Use the same OX interval for conceptual symmetry only when possible.
                # Calling OX again intentionally gives child2 an independent legal cut.
                child2, cuts2 = order_crossover(parent2, parent1, rng)
            else:
                child1, cuts1 = list(parent1), None
                child2, cuts2 = list(parent2), None

            if emit_operator_steps:
                steps.append(
                    SearchStep(
                        step_type=StepType.UPDATE,
                        node_id=child1[-1] if child1 else start,
                        metrics={
                            "stage": "ga_crossover",
                            "generation": generation,
                            "mating_index": mating_index,
                            "operator": "order_crossover_ox",
                            "crossover_rate": crossover_rate,
                            "random_draw": round(crossover_draw, 6),
                            "performed": did_crossover,
                            "child1_cuts": list(cuts1) if cuts1 else None,
                            "child2_cuts": list(cuts2) if cuts2 else None,
                            "child1_before_mutation": _tour_text(
                                _tour_from_chromosome(
                                    start, child1, return_to_start
                                )
                            ),
                            "child2_before_mutation": _tour_text(
                                _tour_from_chromosome(
                                    start, child2, return_to_start
                                )
                            ),
                        },
                    )
                )

            before_mutation1 = list(child1)
            before_mutation2 = list(child2)
            child1, mutation1 = swap_mutation(child1, rng, mutation_rate)
            child2, mutation2 = swap_mutation(child2, rng, mutation_rate)

            if emit_operator_steps:
                steps.append(
                    SearchStep(
                        step_type=StepType.UPDATE,
                        node_id=child1[-1] if child1 else start,
                        metrics={
                            "stage": "ga_mutation",
                            "generation": generation,
                            "mating_index": mating_index,
                            "operator": "swap_mutation",
                            "mutation_rate": mutation_rate,
                            "child1_mutated": mutation1 is not None,
                            "child2_mutated": mutation2 is not None,
                            "child1_swap_indices": list(mutation1)
                            if mutation1
                            else None,
                            "child2_swap_indices": list(mutation2)
                            if mutation2
                            else None,
                            "child1_before": _tour_text(
                                _tour_from_chromosome(
                                    start, before_mutation1, return_to_start
                                )
                            ),
                            "child1_after": _tour_text(
                                _tour_from_chromosome(
                                    start, child1, return_to_start
                                )
                            ),
                            "child2_before": _tour_text(
                                _tour_from_chromosome(
                                    start, before_mutation2, return_to_start
                                )
                            ),
                            "child2_after": _tour_text(
                                _tour_from_chromosome(
                                    start, child2, return_to_start
                                )
                            ),
                        },
                    )
                )

            next_population.append(child1)
            if len(next_population) < population_size:
                next_population.append(child2)

        population = next_population[:population_size]
        evaluated = _evaluate_population(
            population,
            start,
            return_to_start,
            distance_matrix,
        )
        completed_generations = generation

        generation_best_cost, _, generation_best_chromosome = evaluated[0]
        generation_best_tour = _tour_from_chromosome(
            start, generation_best_chromosome, return_to_start
        )
        finite_count = sum(math.isfinite(item[0]) for item in evaluated)

        is_new_global_best = generation_best_cost + _EPSILON < global_best_cost
        if is_new_global_best:
            global_best_cost = float(generation_best_cost)
            global_best_chromosome = list(generation_best_chromosome)
            global_best_generation = generation

        global_best_tour = _tour_from_chromosome(
            start, global_best_chromosome, return_to_start
        )

        finite_costs = [item[0] for item in evaluated if math.isfinite(item[0])]
        average_cost = (
            sum(finite_costs) / len(finite_costs) if finite_costs else math.inf
        )

        steps.append(
            SearchStep(
                step_type=StepType.UPDATE,
                node_id=generation_best_tour[-1],
                metrics={
                    "stage": "ga_generation",
                    "generation": generation,
                    "population_size": len(population),
                    "finite_individuals": finite_count,
                    "generation_best_cost": round(generation_best_cost, 6),
                    "generation_best_fitness": round(
                        get_fitness(generation_best_cost), 12
                    ),
                    "average_cost": round(average_cost, 6)
                    if math.isfinite(average_cost)
                    else math.inf,
                    "global_best_cost": round(global_best_cost, 6),
                    "global_best_generation": global_best_generation,
                    "is_new_global_best": is_new_global_best,
                    "generation_best_tour": _tour_text(generation_best_tour),
                    "global_best_tour": _tour_text(global_best_tour),
                },
            )
        )

        if is_new_global_best:
            steps.append(
                SearchStep(
                    step_type=StepType.UPDATE,
                    node_id=global_best_tour[-1],
                    metrics={
                        "stage": "ga_best",
                        "generation": generation,
                        "is_best": True,
                        "best_cost": round(global_best_cost, 6),
                        "best_fitness": round(get_fitness(global_best_cost), 12),
                        "tour": _tour_text(global_best_tour),
                    },
                )
            )

        if generation % visualize_every == 0 or generation == generations:
            _append_route_visualization(
                steps,
                generation_best_tour,
                path_cache,
                distance_matrix,
                stage="ga_generation_route",
                generation=generation,
                route_cost=generation_best_cost,
                is_global_best=(
                    abs(generation_best_cost - global_best_cost) <= _EPSILON
                ),
            )

    # --------------------------- Final solution ----------------------------
    best_tour = _tour_from_chromosome(
        start, global_best_chromosome, return_to_start
    )
    best_cost = get_tour_cost(best_tour, distance_matrix)
    full_path = _construct_full_path(best_tour, path_cache)

    if not math.isfinite(best_cost) or not full_path:
        return _failure(
            "GA finished but the best tour could not be converted to a road path.",
            start,
            stage="route_construction",
        )

    # Always end with one explicit final route snapshot.
    _append_route_visualization(
        steps,
        best_tour,
        path_cache,
        distance_matrix,
        stage="ga_final_route",
        generation=global_best_generation,
        route_cost=best_cost,
        is_global_best=True,
    )

    steps.append(
        SearchStep(
            step_type=StepType.FINISH,
            node_id=best_tour[-1],
            metrics={
                "stage": "finish",
                "success": True,
                "algorithm": ALGORITHM_NAME,
                "population_size": population_size,
                "generations": completed_generations,
                "crossover_rate": crossover_rate,
                "mutation_rate": mutation_rate,
                "elitism": elitism,
                "tournament_size": tournament_size,
                "best_generation": global_best_generation,
                "total_cost": round(best_cost, 6),
                "best_fitness": round(get_fitness(best_cost), 12),
                "tour": _tour_text(best_tour),
                "step_count": len(steps) + 1,
            },
        )
    )

    goal_visit_order = list(global_best_chromosome)
    message = (
        f"Genetic Algorithm visited {len(goals)} goal(s) using "
        f"population {population_size} for {completed_generations} generation(s); "
        f"best cost {best_cost:.4f} found at generation {global_best_generation}."
    )

    return SearchResult(
        path=full_path,
        steps=steps,
        total_cost=best_cost,
        success=True,
        message=message,
        visited_order=best_tour,
        goal_visit_order=goal_visit_order,
    )


# Alias consistent with other multi-location algorithm modules.
multi_location_genetic_algorithm = genetic_algorithm
