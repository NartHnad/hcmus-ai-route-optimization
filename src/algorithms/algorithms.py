ALGORITHMS = {}
MULTI_LOCATION_ALGORITHMS = {}

try:
    from src.algorithms.dfs import dfs

    ALGORITHMS["Depth-First Search (DFS)"] = dfs
except ImportError:
    pass

try:
    from src.algorithms.mock_multi_location import mock_multi_location_search

    MULTI_LOCATION_ALGORITHMS["Mock Multi-location Search"] = (
        mock_multi_location_search
    )
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


def get_algorithms(route_mode="single"):
    if route_mode == "single":
        return sorted(ALGORITHMS.keys())
    if route_mode == "multi":
        return sorted(MULTI_LOCATION_ALGORITHMS.keys())
    raise ValueError(f"Unknown route mode: {route_mode}")


def run_algorithm(name, graph, start, goal):
    """
    Execute the selected search algorithm.
    """

    if name not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {name}")

    algorithm = ALGORITHMS[name]

    return algorithm(graph, start, goal)


def run_multi_location_algorithm(
    name,
    graph,
    start,
    goals,
    respect_goal_order=False,
):
    """Execute a registered algorithm that accepts multiple goal nodes."""
    if name not in MULTI_LOCATION_ALGORITHMS:
        raise ValueError(f"Unknown multi-location algorithm: {name}")

    return MULTI_LOCATION_ALGORITHMS[name](
        graph,
        start,
        list(goals or []),
        respect_goal_order=bool(respect_goal_order),
    )
