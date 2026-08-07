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

# #NhatHuyChanged: register the multi-location optimizer in the algorithm picker.
try:
    from src.algorithms.mock3_algorithm import mock3_search

    ALGORITHMS["Mock 3 Search"] = mock3_search
except ImportError:
    pass

try:
    from src.algorithms.multi_location import (
        ALGORITHM_NAME,
        multi_location_nearest_neighbor_2opt,
    )

    ALGORITHMS[ALGORITHM_NAME] = multi_location_nearest_neighbor_2opt
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

    # #NhatHuyChanged: accept multi-location routing options without changing
    # the legacy start/goal contract for every other method.
    # The multi-location algorithm accepts a small routing request object so
    # the legacy start/goal contract remains unchanged for every other method.
    if name == "Multi-location (Nearest Neighbor + 2-Opt)":
        if isinstance(goal, dict):
            return algorithm(
                graph,
                start,
                goal.get("locations", []),
                end_id=goal.get("end_id"),
                return_to_start=goal.get("return_to_start", False),
            )
        if isinstance(goal, (list, tuple, set)):
            return algorithm(graph, start, goal)

    return algorithm(graph, start, goal)
