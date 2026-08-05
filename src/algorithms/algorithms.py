ALGORITHMS = {}

try:
    from src.algorithms.dfs import dfs

    ALGORITHMS["Depth-First Search (DFS)"] = dfs
except ImportError:
    pass

try:
    from src.algorithms.bfs import bfs

    ALGORITHMS["Breadth-First Search (BFS)"] = bfs
except ImportError:
    pass

try:
    from src.algorithms.ucs import ucs

    ALGORITHMS["Uniform Cost Search (UCS)"] = ucs
except ImportError:
    pass

try:
    from src.algorithms.a_star import a_star

    ALGORITHMS["A* Search"] = a_star
except ImportError:
    pass


try:
    from src.algorithms.genetic_algorithm import genetic_algorithm

    ALGORITHMS["Genetic Algorithm (GA)"] = genetic_algorithm
except ImportError:
    pass

try:
    from src.algorithms.simulated_annealing import simulated_annealing

    ALGORITHMS["Simulated Annealing (SA)"] = simulated_annealing
except ImportError:
    pass


def get_algorithms():
    return sorted(ALGORITHMS.keys())


def run_algorithm(name, graph, start, goal):
    """
    Execute the selected search algorithm.
    """

    if name not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {name}")

    algorithm = ALGORITHMS[name]

    return algorithm(graph, start, goal)
