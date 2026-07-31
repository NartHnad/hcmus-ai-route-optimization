import heapq

from src.models.models import SearchResult, SearchStep, StepType


def ucs(graph, start_id, goal_id):
    """
    Find the lowest-cost path from start_id to goal_id using
    Uniform-Cost Search (UCS).

    UCS expands the node with the smallest cumulative cost g first,
    so the first time the goal is popped, the path is guaranteed optimal.
    It behaves exactly like A* with a zero heuristic.
    """
    steps = []
    visited_order = []

    if graph is None or start_id not in graph.nodes or goal_id not in graph.nodes:
        steps.append(SearchStep(StepType.FINISH))
        return SearchResult(
            path=[],
            steps=steps,
            total_cost=0.0,
            visited_order=visited_order,
            success=False,
            message="Graph is not loaded or start/goal node not found."
        )

    # Priority queue: stores tuples of (g_score, node_id)
    # UCS only uses the cumulative cost g, there is no heuristic.
    frontier = []
    heapq.heappush(frontier, (0.0, start_id))

    # Track the best known cost to reach each node from the start
    g_score = {start_id: 0.0}

    # Track the parent of each node to reconstruct the path
    # child_id -> (parent_id, edge_to_child)
    came_from = {start_id: (None, None)}

    # Track nodes that have been fully expanded
    visited = set()

    while frontier:
        current_g, current = heapq.heappop(frontier)

        if current in visited:
            continue

        visited.add(current)
        visited_order.append(current)
        steps.append(SearchStep(StepType.EXPAND, node_id=current, metrics={"g": current_g}))

        if current == goal_id:
            path = []
            cursor = goal_id

            # Reconstruct path by following parents backwards
            while cursor is not None:
                path.append(cursor)
                parent, _ = came_from.get(cursor, (None, None))
                cursor = parent

            path.reverse()

            total_cost = current_g

            steps.append(SearchStep(StepType.FINISH, node_id=goal_id))

            return SearchResult(
                path=path,
                steps=steps,
                total_cost=total_cost,
                visited_order=visited_order,
                success=True,
                message=f"UCS found optimal path with cost {total_cost:.2f} after expanding {len(visited_order)} nodes."
            )

        # Explore neighbors
        for edge in graph.get_neighbors(current):
            neighbor = edge.to_node

            if neighbor in visited:
                continue

            tentative_g = current_g + edge.calculate_cost()

            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                # Found a new or better path to neighbor
                came_from[neighbor] = (current, edge)
                g_score[neighbor] = tentative_g

                heapq.heappush(frontier, (tentative_g, neighbor))

                # Emit DISCOVER step for visualization
                steps.append(SearchStep(
                    StepType.DISCOVER,
                    node_id=neighbor,
                    edge_from=current,
                    edge_to=neighbor,
                    metrics={"g": tentative_g}
                ))

    # Queue empty and goal not reached
    steps.append(SearchStep(StepType.FINISH))
    return SearchResult(
        path=[],
        steps=steps,
        total_cost=0.0,
        visited_order=visited_order,
        success=False,
        message=f"No path exists from '{start_id}' to '{goal_id}'."
    )
