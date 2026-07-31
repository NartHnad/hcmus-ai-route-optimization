# src/algorithms/mock_algorithm.py
try:
    from models.models import SearchResult, SearchStep, StepType
except ImportError:
    from src.models.models import SearchResult, SearchStep, StepType


def mock_search(graph, start_id, goal_id):
    """
    Mock search algorithm returning a SearchResult for GUI testing.

    This generates a simple, predictable sequence of SearchSteps
    following the standard StepType lifecycle.
    """
    steps = []

    if graph is None or start_id not in graph.nodes or goal_id not in graph.nodes:
        return SearchResult(
            path=[],
            steps=[SearchStep(StepType.FINISH)],
            total_cost=0.0,
            success=False,
        )

    current = start_id
    steps.append(SearchStep(StepType.EXPAND, node_id=current))

    path = [current]
    total_cost = 0.0

    # Inspect neighbors of start node
    for edge in graph.adjacency_list.get(current, []):
        # 1. Discover the neighbor node
        steps.append(
            SearchStep(
                StepType.DISCOVER,
                node_id=edge.to_node,
                edge_from=edge.from_node,
                edge_to=edge.to_node,
                metrics={"g": edge.distance},
            )
        )

        # 2. Expand it
        steps.append(SearchStep(StepType.EXPAND, node_id=edge.to_node))

        # Build mock path
        path.append(edge.to_node)
        total_cost += edge.distance
        break

    # Finalize search
    steps.append(SearchStep(StepType.FINISH, node_id=goal_id))

    return SearchResult(
        path=path,
        steps=steps,
        total_cost=total_cost,
        success=True,
        visited_order=path,
    )

