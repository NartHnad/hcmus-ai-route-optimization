def mock3_search(graph, start_id, goal_id):
    """
    A mock DFS-like search algorithm for GUI testing.

    It traverses the graph in depth-first order until the goal is found
    or all reachable nodes have been visited.

    Generated step types:
        - visit_node
        - inspect_edge
        - path_edge
        - finish
    """

    if graph is None:
        return [{"type": "finish", "path": []}]

    if start_id not in graph.nodes:
        return [{"type": "finish", "path": []}]

    steps = []

    visited = set()
    stack = [(start_id, [start_id])]

    while stack:

        current, path = stack.pop()

        if current in visited:
            continue

        visited.add(current)

        steps.append({
            "type": "visit_node",
            "node": current,
        })

        if current == goal_id:

            # Highlight the final path
            for i in range(len(path) - 1):
                steps.append({
                    "type": "path_edge",
                    "from": path[i],
                    "to": path[i + 1],
                })

            steps.append({
                "type": "finish",
                "path": path,
            })

            return steps

        # Reverse so the traversal order is deterministic
        neighbors = list(graph.adjacency_list.get(current, []))
        neighbors.reverse()

        for edge in neighbors:

            steps.append({
                "type": "inspect_edge",
                "from": edge.from_node,
                "to": edge.to_node,
            })

            if edge.to_node not in visited:

                stack.append(
                    (
                        edge.to_node,
                        path + [edge.to_node],
                    )
                )

    steps.append({
        "type": "finish",
        "path": [],
    })

    return steps