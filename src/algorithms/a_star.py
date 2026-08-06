import heapq

from src.models.models import SearchResult, SearchStep, StepType
from src.utils.heuristics import geographic_heuristic



def a_star(graph, start_id, goal_id):
    """
    Find the optimal path from start_id to goal_id using A* Search.

    A* uses both the actual cost from start (g) and a heuristic estimate to the goal (h)
    to decide which node to explore next. This implementation uses geographic distance
    (Haversine) as the heuristic if coordinates are available.
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
            message="Graph is not loaded or start/goal node not found.",
        )


    # Priority queue: stores tuples of (f_score, g_score, node_id)
    # Note: We include g_score in the tuple so that in case of an f_score tie,
    # the node with the lower g_score (closer to start) is preferred, or just to avoid tuple comparison errors on node_id string
    open_set = []
    heapq.heappush(open_set, (0.0, 0.0, start_id))

    # Track the best known cost to reach each node from the start
    g_score = {start_id: 0.0}

    # Track the parent of each node to reconstruct the path
    # child_id -> (parent_id, edge_to_child)
    came_from = {start_id: (None, None)}

    # Track nodes that have been fully expanded
    visited = set()

    while open_set:
        current_f, current_g, current = heapq.heappop(open_set)

        if current in visited:
            continue

        visited.add(current)
        visited_order.append(current)
        steps.append(
            SearchStep(
                StepType.EXPAND,
                node_id=current,
                metrics={"g": current_g, "f": current_f},
            )
        )

        if current == goal_id:
            path = []
            path_edges = []
            cursor = goal_id

            # Reconstruct path by following parents backwards
            while cursor is not None:
                path.append(cursor)
                parent, edge_to_cursor = came_from.get(cursor, (None, None))
                if edge_to_cursor is not None:
                    path_edges.append(edge_to_cursor)
                cursor = parent

            path.reverse()
            path_edges.reverse()

            total_cost = current_g

            steps.append(SearchStep(StepType.FINISH, node_id=goal_id))

            return SearchResult(
                path=path,
                steps=steps,
                total_cost=total_cost,
                visited_order=visited_order,
                success=True,
                message=f"A* found optimal path with cost {total_cost:.2f} after expanding {len(visited_order)} nodes.",
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
                h = geographic_heuristic(neighbor)
                f = tentative_g + h

                heapq.heappush(open_set, (f, tentative_g, neighbor))

                # Emit DISCOVER step for visualization
                steps.append(
                    SearchStep(
                        StepType.DISCOVER,
                        node_id=neighbor,
                        edge_from=current,
                        edge_to=neighbor,
                        metrics={"g": tentative_g, "h": h, "f": f},
                    )
                )

    # Queue empty and goal not reached
    steps.append(SearchStep(StepType.FINISH))
    return SearchResult(
        path=[],
        steps=steps,
        total_cost=0.0,
        visited_order=visited_order,
        success=False,
        message=f"No path exists from '{start_id}' to '{goal_id}'.",
    )
