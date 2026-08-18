import heapq

from src.models.models import SearchResult, SearchStep, StepType
from src.utils.heuristics import geographic_heuristic


def beam_search(graph, start_id, goal_id, beam_width=10):
    """Find a route using heuristic, bounded-width beam search.

    Candidates are ranked by ``f(n) = g(n) + h(n)``, where ``h`` is the
    project's shared geographic heuristic. Candidates outside the beam are
    deliberately pruned, so the returned route is not guaranteed to have the
    minimum cost.
    """
    steps = []
    visited_order = []

    if not isinstance(beam_width, int) or beam_width <= 0:
        raise ValueError("beam_width must be a positive integer")

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

    def build_success_result():
        path = []
        path_edges = []
        cursor = goal_id

        while cursor is not None:
            path.append(cursor)
            parent, edge_to_cursor = came_from[cursor]
            if edge_to_cursor is not None:
                path_edges.append(edge_to_cursor)
            cursor = parent

        path.reverse()
        path_edges.reverse()
        total_cost = sum(edge.calculate_cost() for edge in path_edges)
        steps.append(SearchStep(StepType.FINISH, node_id=goal_id))

        return SearchResult(
            path=path,
            steps=steps,
            total_cost=total_cost,
            visited_order=visited_order,
            success=True,
            message=(
                f"Beam Search (beam_width={beam_width}) found a path after "
                f"exploring {len(visited_order)} node(s)."
            ),
        )

    current_beam = [start_id]
    discovered = {start_id}
    came_from = {start_id: (None, None)}
    path_cost = {start_id: 0.0}

    while current_beam:
        candidate_by_node = {}

        for current in current_beam:
            visited_order.append(current)
            steps.append(SearchStep(StepType.EXPAND, node_id=current))

            if current == goal_id:
                return build_success_result()

            for edge in graph.get_neighbors(current):
                neighbor = edge.to_node
                if neighbor in discovered:
                    continue

                edge_cost = edge.calculate_cost()
                tentative_g = path_cost[current] + edge_cost
                h = geographic_heuristic(graph, neighbor, goal_id)
                f = tentative_g + h
                candidate = (f, tentative_g, neighbor, current, edge, h)

                previous = candidate_by_node.get(neighbor)
                if previous is None or candidate[:2] < previous[:2]:
                    candidate_by_node[neighbor] = candidate

        if not candidate_by_node:
            break

        next_candidates = heapq.nsmallest(
            beam_width,
            candidate_by_node.values(),
            key=lambda candidate: candidate[:3],
        )

        current_beam = []
        for priority, tentative_g, neighbor, parent, edge, h in next_candidates:
            discovered.add(neighbor)
            came_from[neighbor] = (parent, edge)
            path_cost[neighbor] = tentative_g
            current_beam.append(neighbor)
            steps.append(
                SearchStep(
                    StepType.DISCOVER,
                    node_id=neighbor,
                    edge_from=parent,
                    edge_to=neighbor,
                    metrics={"g": tentative_g, "h": h, "f": priority},
                )
            )

    # There is no complete route to price when the goal is not reached.
    total_cost = 0.0
    steps.append(
        SearchStep(
            StepType.FINISH,
            metrics={"total_cost": total_cost},
        )
    )
    return SearchResult(
        path=[],
        steps=steps,
        total_cost=total_cost,
        visited_order=visited_order,
        success=False,
        message=(
            f"No path found within beam width {beam_width} from "
            f"'{start_id}' to '{goal_id}'."
        ),
    )
