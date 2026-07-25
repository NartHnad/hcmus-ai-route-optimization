from collections import deque

from src.models.models import SearchResult


def bfs(graph, start_id, goal_id):
    """
    Find a path from start_id to goal_id using Breadth-First Search.

    BFS explores the graph level by level, so the returned path has the
    fewest edges among all reachable paths. Edge costs are calculated only
    for reporting; they do not affect which path BFS chooses.
    """
    steps = []
    visited_order = []

    # Validate all inputs before starting the search.
    if graph is None:
        steps.append({"type": "finish", "path": []})
        return SearchResult(
            path=[],
            steps=steps,
            total_cost=0.0,
            visited_order=visited_order,
            success=False,
            message="Graph is not loaded.",
        )

    if start_id not in graph.nodes:
        steps.append({"type": "finish", "path": []})
        return SearchResult(
            path=[],
            steps=steps,
            total_cost=0.0,
            visited_order=visited_order,
            success=False,
            message=f"Start node '{start_id}' was not found.",
        )

    if goal_id not in graph.nodes:
        steps.append({"type": "finish", "path": []})
        return SearchResult(
            path=[],
            steps=steps,
            total_cost=0.0,
            visited_order=visited_order,
            success=False,
            message=f"Goal node '{goal_id}' was not found.",
        )

    queue = deque([start_id])
    visited = {start_id}

    # child_id -> (parent_id, edge from parent to child)
    came_from = {start_id: (None, None)}

    while queue:
        current = queue.popleft()
        visited_order.append(current)
        steps.append({"type": "visit_node", "node": current})

        if current == goal_id:
            path = []
            path_edges = []
            cursor = goal_id

            # Follow parent links from the goal back to the start.
            while cursor is not None:
                path.append(cursor)
                parent, edge_to_cursor = came_from[cursor]

                if edge_to_cursor is not None:
                    path_edges.append(edge_to_cursor)

                cursor = parent

            # The reconstruction above is goal -> start, so reverse it.
            path.reverse()
            path_edges.reverse()

            total_cost = 0.0
            for edge in path_edges:
                total_cost += edge.calculate_cost()
                steps.append(
                    {
                        "type": "path_edge",
                        "from": edge.from_node,
                        "to": edge.to_node,
                    }
                )

            steps.append({"type": "finish", "path": path})

            return SearchResult(
                path=path,
                steps=steps,
                total_cost=total_cost,
                visited_order=visited_order,
                success=True,
                message=(
                    "BFS found a path after exploring " f"{len(visited_order)} node(s)."
                ),
            )

        for edge in graph.get_neighbors(current):
            neighbor = edge.to_node

            steps.append(
                {
                    "type": "inspect_edge",
                    "from": current,
                    "to": neighbor,
                }
            )

            if neighbor in visited:
                continue

            # Mark a node when it enters the queue to avoid duplicate entries.
            visited.add(neighbor)
            came_from[neighbor] = (current, edge)
            queue.append(neighbor)

    # The queue is empty, so the goal is not reachable from the start.
    steps.append({"type": "finish", "path": []})
    return SearchResult(
        path=[],
        steps=steps,
        total_cost=0.0,
        visited_order=visited_order,
        success=False,
        message=f"No path exists from '{start_id}' to '{goal_id}'.",
    )
