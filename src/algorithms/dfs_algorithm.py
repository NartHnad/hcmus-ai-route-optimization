

def dfs(graph, start_id, goal_id):
    """
    Depth-First Search (DFS) algorithm for pathfinding.

    Parameters:
    - graph: The graph to search, represented as an adjacency list.
    - start_id: The ID of the starting node.
    - goal_id: The ID of the goal node.

    Returns:
    
    """
    steps = []
    visited = set()
    stack = [(start_id, [start_id])]

    while stack:
        current, path = stack.pop()
        if current in visited:
            continue

        visited.add(current)
        steps.append({"type": "visit_node", "node": current})

        if current == goal_id:
            steps.append({"type": "finish", "path": path})
            return steps

        for edge in graph.adjacency_list.get(current, []):
            if edge.to_node not in visited:
                steps.append({
                    "type": "inspect_edge",
                    "from": edge.from_node,
                    "to": edge.to_node,
                })
                stack.append((edge.to_node, path + [edge.to_node]))

    steps.append({"type": "finish", "path": []})
    return steps