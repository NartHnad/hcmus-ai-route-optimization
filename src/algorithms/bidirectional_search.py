# #NhatHuyChanged: add optimal weighted Bidirectional Search for single routes.
"""Bidirectional Uniform-Cost Search for directed road graphs.

The search runs Dijkstra/UCS from the start over outgoing edges and from the
goal over an incoming-edge index.  It therefore respects one-way streets and
optimizes the same non-negative composite edge cost used by the other project
algorithms.
"""

from __future__ import annotations

import heapq
import math

from src.constants import StepType
from src.models.models import SearchResult, SearchStep


ALGORITHM_NAME = "Bidirectional Search (UCS)"
_EPSILON = 1e-12


def _edge_cost(edge) -> float:
    """Return a usable non-negative project cost, or infinity if invalid."""

    cost = float(edge.calculate_cost())
    return cost if math.isfinite(cost) and cost >= 0.0 else math.inf


def _reverse_adjacency(graph) -> dict[str, list]:
    """Index each original directed edge by its destination node."""

    if hasattr(graph, "incoming_adjacency_list"):
        return graph.incoming_adjacency_list

    # Compatibility fallback for external graph implementations.
    incoming = {node_id: [] for node_id in graph.nodes}
    for outgoing_edges in graph.adjacency_list.values():
        for edge in outgoing_edges:
            if edge.from_node in graph.nodes and edge.to_node in graph.nodes:
                incoming.setdefault(edge.to_node, []).append(edge)
    return incoming


def _peek_valid(frontier, distances, settled) -> float:
    """Discard stale heap entries and return the next unsettled distance."""

    while frontier:
        cost, node_id = frontier[0]
        if node_id in settled or cost > distances.get(node_id, math.inf) + _EPSILON:
            heapq.heappop(frontier)
            continue
        return cost
    return math.inf


def _pop_valid(frontier, distances, settled):
    """Pop the next current heap entry after stale entries are removed."""

    _peek_valid(frontier, distances, settled)
    if not frontier:
        return None
    return heapq.heappop(frontier)


def _reconstruct_path(start_id, goal_id, meeting, forward_parent, backward_parent):
    """Join start -> meeting and meeting -> goal parent chains."""

    forward_path = []
    cursor = meeting
    while cursor is not None:
        forward_path.append(cursor)
        cursor = forward_parent.get(cursor)
    forward_path.reverse()

    backward_path = []
    cursor = backward_parent.get(meeting)
    while cursor is not None:
        backward_path.append(cursor)
        cursor = backward_parent.get(cursor)

    path = forward_path + backward_path
    if not path or path[0] != start_id or path[-1] != goal_id:
        return []
    return path


def _failure(message: str, node_id=None, visited_order=None, steps=None) -> SearchResult:
    steps = list(steps or [])
    steps.append(
        SearchStep(
            StepType.FINISH,
            node_id=node_id,
            metrics={"success": False, "optimal": False},
        )
    )
    return SearchResult(
        path=[],
        steps=steps,
        total_cost=0.0,
        visited_order=list(visited_order or []),
        success=False,
        message=message,
    )


def bidirectional_search(graph, start_id: str, goal_id: str) -> SearchResult:
    """Find an optimal route using weighted searches from both endpoints.

    The stop rule ``min_forward + min_backward >= best_path`` is the standard
    lower-bound condition for bidirectional Dijkstra on non-negative edges.
    """

    if graph is None:
        return _failure("Graph is not loaded.")
    if start_id not in graph.nodes:
        return _failure(f"Start node '{start_id}' was not found.")
    if goal_id not in graph.nodes:
        return _failure(f"Goal node '{goal_id}' was not found.")

    if start_id == goal_id:
        steps = [
            SearchStep(
                StepType.EXPAND,
                node_id=start_id,
                metrics={"g": 0.0, "search_direction": "forward"},
            ),
            SearchStep(
                StepType.FINISH,
                node_id=start_id,
                metrics={
                    "g": 0.0,
                    "meeting_node": start_id,
                    "forward_expanded": 1,
                    "backward_expanded": 0,
                    "unique_expanded": 1,
                    "optimal": True,
                },
            ),
        ]
        return SearchResult(
            path=[start_id],
            steps=steps,
            total_cost=0.0,
            visited_order=[start_id],
            success=True,
            message="Start and goal are the same node; optimal cost is 0.00.",
        )

    incoming = _reverse_adjacency(graph)
    forward_frontier = [(0.0, start_id)]
    backward_frontier = [(0.0, goal_id)]
    forward_distance = {start_id: 0.0}
    backward_distance = {goal_id: 0.0}
    forward_parent = {start_id: None}
    # node -> next node on the original directed route toward the goal
    backward_parent = {goal_id: None}
    forward_settled = set()
    backward_settled = set()
    visited_order = []
    globally_visited = set()
    steps = []
    best_cost = math.inf
    meeting = None

    def record_expansion(node_id, cost, direction):
        if node_id not in globally_visited:
            globally_visited.add(node_id)
            visited_order.append(node_id)
        steps.append(
            SearchStep(
                StepType.EXPAND,
                node_id=node_id,
                metrics={"g": cost, "search_direction": direction},
            )
        )

    def consider_meeting(node_id, candidate_cost):
        nonlocal best_cost, meeting
        if not math.isfinite(candidate_cost):
            return False
        candidate_key = (candidate_cost, str(node_id))
        current_key = (best_cost, str(meeting)) if meeting is not None else None
        if current_key is None or candidate_key < current_key:
            best_cost = candidate_cost
            meeting = node_id
            return True
        return False

    while forward_frontier and backward_frontier:
        min_forward = _peek_valid(
            forward_frontier, forward_distance, forward_settled
        )
        min_backward = _peek_valid(
            backward_frontier, backward_distance, backward_settled
        )
        if not math.isfinite(min_forward) or not math.isfinite(min_backward):
            break
        if (
            forward_settled
            and backward_settled
            and min_forward + min_backward >= best_cost - _EPSILON
        ):
            break

        if min_forward <= min_backward:
            popped = _pop_valid(
                forward_frontier, forward_distance, forward_settled
            )
            if popped is None:
                break
            current_cost, current = popped
            forward_settled.add(current)
            record_expansion(current, current_cost, "forward")

            if current in backward_distance:
                consider_meeting(
                    current, current_cost + backward_distance[current]
                )

            for edge in graph.get_neighbors(current):
                edge_cost = _edge_cost(edge)
                if not math.isfinite(edge_cost):
                    continue
                neighbor = edge.to_node
                if neighbor not in graph.nodes:
                    continue
                candidate = current_cost + edge_cost
                previous = forward_distance.get(neighbor, math.inf)
                if candidate + _EPSILON >= previous:
                    continue

                first_discovery = not math.isfinite(previous)
                forward_distance[neighbor] = candidate
                forward_parent[neighbor] = current
                heapq.heappush(forward_frontier, (candidate, neighbor))
                found_meeting = False
                if neighbor in backward_distance:
                    found_meeting = consider_meeting(
                        neighbor, candidate + backward_distance[neighbor]
                    )
                metrics = {
                    "g": candidate,
                    "search_direction": "forward",
                }
                if found_meeting:
                    metrics["meeting_cost"] = best_cost
                steps.append(
                    SearchStep(
                        StepType.DISCOVER if first_discovery else StepType.UPDATE,
                        node_id=neighbor,
                        edge_from=current,
                        edge_to=neighbor,
                        metrics=metrics,
                        frontier_position="priority",
                    )
                )
        else:
            popped = _pop_valid(
                backward_frontier, backward_distance, backward_settled
            )
            if popped is None:
                break
            current_cost, current = popped
            backward_settled.add(current)
            record_expansion(current, current_cost, "backward")

            if current in forward_distance:
                consider_meeting(
                    current, current_cost + forward_distance[current]
                )

            # Traverse an original edge predecessor -> current in reverse.
            for edge in incoming.get(current, []):
                edge_cost = _edge_cost(edge)
                if not math.isfinite(edge_cost):
                    continue
                predecessor = edge.from_node
                if predecessor not in graph.nodes:
                    continue
                candidate = current_cost + edge_cost
                previous = backward_distance.get(predecessor, math.inf)
                if candidate + _EPSILON >= previous:
                    continue

                first_discovery = not math.isfinite(previous)
                backward_distance[predecessor] = candidate
                backward_parent[predecessor] = current
                heapq.heappush(backward_frontier, (candidate, predecessor))
                found_meeting = False
                if predecessor in forward_distance:
                    found_meeting = consider_meeting(
                        predecessor, candidate + forward_distance[predecessor]
                    )
                metrics = {
                    "g": candidate,
                    "search_direction": "backward",
                }
                if found_meeting:
                    metrics["meeting_cost"] = best_cost
                steps.append(
                    SearchStep(
                        StepType.DISCOVER if first_discovery else StepType.UPDATE,
                        node_id=predecessor,
                        # Keep the event in the real road direction for rendering.
                        edge_from=predecessor,
                        edge_to=current,
                        metrics=metrics,
                        frontier_position="priority",
                    )
                )

    if meeting is None or not math.isfinite(best_cost):
        return _failure(
            f"No path exists from '{start_id}' to '{goal_id}'.",
            visited_order=visited_order,
            steps=steps,
        )

    path = _reconstruct_path(
        start_id,
        goal_id,
        meeting,
        forward_parent,
        backward_parent,
    )
    if not path:
        return _failure(
            "The two search frontiers met, but the route could not be reconstructed.",
            node_id=meeting,
            visited_order=visited_order,
            steps=steps,
        )

    finish_metrics = {
        "g": best_cost,
        "meeting_node": meeting,
        "forward_expanded": len(forward_settled),
        "backward_expanded": len(backward_settled),
        "unique_expanded": len(forward_settled | backward_settled),
        "optimal": True,
    }
    steps.append(
        SearchStep(
            StepType.FINISH,
            node_id=meeting,
            metrics=finish_metrics,
        )
    )
    return SearchResult(
        path=path,
        steps=steps,
        total_cost=best_cost,
        visited_order=visited_order,
        success=True,
        message=(
            "Bidirectional UCS found an optimal path with cost "
            f"{best_cost:.2f}; the searches met at '{meeting}' after expanding "
            f"{finish_metrics['unique_expanded']} unique node(s)."
        ),
    )
