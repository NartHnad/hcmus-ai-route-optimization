from src.models.models import RouteRequest

ALGORITHMS = {}
MULTI_LOCATION_ALGORITHMS = {}

# ====================
# IMPORT ALGORITHMS
# ====================

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
    from src.algorithms.beam_search import beam_search

    ALGORITHMS["Beam Search Algorithm"] = beam_search
except ImportError:
    pass


# ====================
# IMPORT MULTI LOCATION ALGORITHMS
# ====================

try:
    from src.algorithms.mock_multi_location import mock_multi_location_search

    MULTI_LOCATION_ALGORITHMS["Mock Multi-location Search"] = mock_multi_location_search
except ImportError:
    pass

try:
    from src.algorithms.simulated_annealing import simulated_annealing

    MULTI_LOCATION_ALGORITHMS["Simulated Annealing (SA)"] = simulated_annealing
except ImportError:
    pass

# #NhatHuyChanged: expose the deterministic multi-location optimizer.
try:
    from src.algorithms.nearest_neighbor_2opt import (
        ALGORITHM_NAME as NEAREST_NEIGHBOR_2OPT_NAME,
        nearest_neighbor_2opt,
    )

    MULTI_LOCATION_ALGORITHMS[NEAREST_NEIGHBOR_2OPT_NAME] = nearest_neighbor_2opt
except ImportError:
    pass


# Get Algorithms from dictionary
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
    return_to_start=False,
):
    """Execute a registered algorithm that accepts multiple goal nodes."""
    if name not in MULTI_LOCATION_ALGORITHMS:
        raise ValueError(f"Unknown multi-location algorithm: {name}")

    return MULTI_LOCATION_ALGORITHMS[name](
        graph,
        start,
        list(goals or []),
        respect_goal_order=bool(respect_goal_order),
        return_to_start=bool(return_to_start),
    )


def run_route_request(name, graph, request: RouteRequest):
    """
    Dispatch an immutable route request to its compatible registry.
    """

    if request.route_mode == "single":
        if not request.delivery_nodes:
            raise ValueError("A route request requires at least one goal node.")

        return run_algorithm(name, graph, request.start_node, request.delivery_nodes[0])

    if request.route_mode == "multi":
        return run_multi_location_algorithm(
            name,
            graph,
            request.start_node,
            request.delivery_nodes,
            respect_goal_order=request.respect_goal_order,
        )

    return run_multi_location_algorithm(
        name,
        graph,
        request.start_node,
        request.delivery_nodes,
        respect_goal_order=request.respect_goal_order,
        return_to_start=request.return_to_start,
    )

