# src/algorithms/mock_algorithm.py


def mock_search(graph, start_id, goal_id):
    """
    Mock search algorithm for testing GUI step-by-step animation.

    This is not a real pathfinding algorithm yet. It only emits a small,
    predictable list of steps that matches the GUI contract in PLAN.md:

    - visit_node: highlight a node
    - inspect_edge: highlight an inspected edge
    - path_edge: highlight an edge as part of the current path
    - finish: signal the animation is complete
    """
    steps = []

    if graph is None or start_id not in graph.nodes:
        return [{"type": "finish", "path": []}]

    current = start_id
    path = [current]
    steps.append({"type": "visit_node", "node": current})

    for edge in graph.adjacency_list.get(current, []):
        steps.append({
            "type": "inspect_edge",
            "from": edge.from_node,
            "to": edge.to_node,
        })

        steps.append({
            "type": "visit_node",
            "node": edge.to_node,
        })

        steps.append({
            "type": "path_edge",
            "from": edge.from_node,
            "to": edge.to_node,
        })

        path.append(edge.to_node)
        break

    steps.append({"type": "finish", "path": path})

    return steps
