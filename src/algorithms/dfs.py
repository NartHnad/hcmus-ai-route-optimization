try:
    from models.models import SearchResult, SearchStep, StepType
except ImportError:
    from src.models.models import SearchResult, SearchStep, StepType


def dfs(graph, start_id, goal_id):
    """
    Depth-First Search (DFS) algorithm for pathfinding.

    Parameters:
    - graph: The graph to search.
    - start_id: The ID of the starting node.
    - goal_id: The ID of the goal node.

    Returns:
    - SearchResult: An object containing the path, steps taken, total cost, and success status.
    """
    steps = []
    if graph is None or start_id not in graph.nodes or goal_id not in graph.nodes:
        return SearchResult(
            path=[],
            steps=[SearchStep(StepType.FINISH)],
            total_cost=0.0,
            success=False,
            message="Invalid graph or start/goal nodes.",
        )

    visited = set()
    stack = [(start_id, [start_id])]

    while stack:
        current, path = stack.pop()
        if current in visited:
            continue

        visited.add(current)
        # DFS expansion step
        steps.append(SearchStep(StepType.EXPAND, node_id=current))

        if current == goal_id:
            steps.append(SearchStep(StepType.FINISH, node_id=goal_id))

            # Tính toán total cost của đường đi tìm thấy
            total_cost = 0.0
            for i in range(len(path) - 1):
                edge = graph.get_edge(path[i], path[i + 1])
                if edge:
                    total_cost += edge.distance

            return SearchResult(
                path=path,
                steps=steps,
                total_cost=total_cost,
                success=True,
                message=f"DFS completed. Found path from {start_id} to {goal_id} with cost {total_cost:.1f}.",
                visited_order=list(visited),
            )

        # Duyệt qua các node láng giềng
        for edge in graph.adjacency_list.get(current, []):
            if edge.to_node not in visited:
                # Discovering a new node/edge
                steps.append(
                    SearchStep(
                        StepType.DISCOVER,
                        node_id=edge.to_node,
                        edge_from=edge.from_node,
                        edge_to=edge.to_node,
                    )
                )
                stack.append((edge.to_node, path + [edge.to_node]))

    steps.append(SearchStep(StepType.FINISH, node_id=goal_id))
    return SearchResult(
        path=[],
        steps=steps,
        total_cost=0.0,
        success=False,
        message=f"DFS finished. Goal {goal_id} not reachable from {start_id}.",
        visited_order=list(visited),
    )