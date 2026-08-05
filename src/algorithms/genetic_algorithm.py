import random

from src.models.models import SearchResult, SearchStep, StepType


def path_cost(graph, path, mode="optimal"):
    """ "
    Calculate the total cost of a given path based on the specified mode.
    """

    total = 0.0

    for i in range(len(path) - 1):
        # Get the edge between the current node and the next node in the path
        edge = graph.get_edge(path[i], path[i + 1])

        if edge is None:
            # If there's no edge return inf
            return float("inf")

        # Calculate the cost
        total += edge.calculate_cost(mode=mode)

    return total


def fitness_function(graph, chromosome, mode="optimal"):
    """
    Fitness function for the genetic algorithm.
    The fitness is inversely proportional to the path cost.
    """
    cost = path_cost(graph, chromosome, mode=mode)

    if cost == float("inf"):
        return 0.0  # Invalid paths have zero fitness

    return 1.0 / (1.0 + cost)


def random_path(graph, start_id, goal_id, max_steps=30):
    """
    Generate a random valid path from start_id to goal_id using Self-Avoiding Random Walk.
    This function ensures that the generated path is valid and does not contain cycles.
    """
    path = [start_id]
    current = start_id
    visited = {start_id}

    for _ in range(max_steps):
        if current == goal_id:
            return path

        neighbors = [
            edge.to_node
            for edge in graph.get_neighbors(current)
            if edge.to_node not in visited
        ]

        if not neighbors:
            break

        next_node = random.choice(neighbors)

        path.append(next_node)
        visited.add(next_node)
        current = next_node

    return path if path[-1] == goal_id else None


def select_parent(population, fitness):
    tournament = random.sample(population, min(3, len(population)))

    return max(tournament, key=fitness)


def crossover(parent1, parent2):
    # Find the common nodes between parents
    common = set(parent1[1:-1]) & set(parent2[1:-1])

    if not common:
        return parent1.copy()

    cross_node = random.choice(list(common))

    i = parent1.index(cross_node)
    j = parent2.index(cross_node)

    # Combine the two parents at the crossover point
    child = parent1[:i] + parent2[j:]

    # Remove consecutive duplicates
    cleaned = [child[0]]
    seen = {child[0]}

    for node in child[1:]:
        if node in seen:
            # Remove nodes in loop
            while cleaned and cleaned[-1] != node:
                seen.remove(cleaned.pop())
        else:
            cleaned.append(node)
            seen.add(node)

    # Fix: lost goal_id in the child path after removing loops
    # If the last node is not the goal_id, append it if it's in the original child path
    # fallback to parent1's last node if goal_id is not present
    if not cleaned or cleaned[-1] != parent1[-1]:
        return parent1.copy()

    return cleaned


def mutate(graph, path, goal_id, max_steps=30):
    """
    Mutate a path by replacing its suffix with a new random walk.
    """
    if len(path) < 3:
        return path

    idx = random.randint(1, len(path) - 2)

    prefix = path[:idx]
    current = prefix[-1]

    visited = set(prefix)
    new_path = prefix.copy()

    for _ in range(max_steps):
        if current == goal_id:
            break

        neighbors = [
            edge.to_node
            for edge in graph.get_neighbors(current)
            if edge.to_node not in visited
        ]

        if not neighbors:
            break

        nxt = random.choice(neighbors)

        new_path.append(nxt)
        visited.add(nxt)
        current = nxt

    return new_path if new_path[-1] == goal_id else path


def genetic_algorithm(
    graph,
    start_id,
    goal_id,
    population_size=50,
    generations=100,
    mutation_rate: float = 0.2,
    mode: str = "optimal",
):
    """
    Genetic Algorithm for route optimization.

    Chromosome = list of node IDs representing a valid path
    from start_id to goal_id.

    Chọn lọc: Selection, Lai ghép: Crossover, Đột biến: Mutation, Hàm độ thích nghi: Fitness Function
    """

    steps = []

    # Initial Population
    population = []
    max_attempts = population_size * 20
    attempts = 0

    while len(population) < population_size and attempts < max_attempts:
        attempts += 1

        candidate = random_path(graph, start_id, goal_id, max_steps=30)

        if candidate and candidate[-1] == goal_id:
            population.append(candidate)

            # Emit all edges of the generated candidate
            for i in range(len(candidate) - 1):
                steps.append(
                    SearchStep(
                        StepType.DISCOVER,
                        node_id=candidate[i + 1],
                        edge_from=candidate[i],
                        edge_to=candidate[i + 1],
                        metrics={"path_length": len(candidate)},
                    )
                )

    if not population:
        return SearchResult(
            success=False,
            message="Unable to generate any valid path",
            steps=steps,
        )

    # Fitness closure
    def calculate_fitness(path):
        return fitness_function(graph, path, mode=mode)

    # Best initial solution
    best_path = min(population, key=lambda p: path_cost(graph, p, mode=mode))
    best_cost = path_cost(graph, best_path, mode=mode)

    # Evolution loop
    for generation in range(generations):
        # Sort population by fitness (lower cost is better)
        population.sort(key=lambda p: path_cost(graph, p, mode=mode))

        current_best = population[0]
        current_best_cost = path_cost(graph, current_best, mode=mode)

        if current_best_cost < best_cost:
            best_path = current_best
            best_cost = current_best_cost

        # Emit the current best path
        for i in range(len(best_path) - 1):
            steps.append(
                SearchStep(
                    StepType.UPDATE,
                    node_id=best_path[i + 1],
                    edge_from=best_path[i],
                    edge_to=best_path[i + 1],
                    metrics={
                        "generation": generation,
                        "best_cost": round(best_cost, 2),
                    },
                )
            )

        # Add EXPAND step representing the current population
        sample_node = current_best[min(generation, len(current_best) - 1)]
        steps.append(
            SearchStep(
                StepType.EXPAND,
                node_id=sample_node,
                metrics={
                    "generation": generation,
                    "population_size": len(population),
                    "current_cost": round(current_best_cost, 2),
                },
            )
        )

        # Elitism: keep top 20%
        elite_count = max(1, population_size // 5)
        new_population = population[:elite_count].copy()

        # Generate new generation
        gen_attempts = 0
        while (
            len(new_population) < population_size and gen_attempts < population_size * 5
        ):
            gen_attempts += 1

            parent1 = select_parent(population, calculate_fitness)
            parent2 = select_parent(population, calculate_fitness)

            child = crossover(parent1, parent2)

            if random.random() < mutation_rate:
                child = mutate(graph, child, goal_id)

            if (
                child
                and child[-1] == goal_id
                and path_cost(graph, child, mode=mode) < float("inf")
            ):
                new_population.append(child)

        population = new_population

    # FINAL RESULT
    total_cost = path_cost(graph, best_path, mode=mode)

    # EMIT FINAL PATH FOR UI DRAWING
    for i in range(len(best_path) - 1):
        steps.append(
            SearchStep(
                StepType.UPDATE,
                node_id=best_path[i + 1],
                edge_from=best_path[i],
                edge_to=best_path[i + 1],
                metrics={"final_path": True},
            )
        )

    steps.append(
        SearchStep(
            StepType.FINISH,
            node_id=goal_id,
            metrics={
                "total_cost": round(total_cost, 2),
                "path_length": len(best_path),
            },
        )
    )

    return SearchResult(
        path=best_path,
        steps=steps,
        total_cost=total_cost,
        success=True,
        message=f"Genetic Algorithm found a route after {generations} generations.",
        visited_order=best_path,
    )
