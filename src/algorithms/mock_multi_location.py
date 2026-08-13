import re

from src.algorithms.a_star import a_star
from src.constants import StepType
from src.models.models import SearchResult, SearchStep


def _natural_node_key(node_id):
    """Return a deterministic, human-friendly key for mock route ordering."""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", str(node_id))
    ]


def _clone_leg_step(step, leg_index, leg_count, leg_start, leg_goal):
    metrics = dict(getattr(step, "metrics", {}) or {})
    metrics.update(
        {
            "leg_index": leg_index,
            "leg_count": leg_count,
            "leg_start": leg_start,
            "leg_goal": leg_goal,
        }
    )
    return SearchStep(
        step_type=step.step_type,
        node_id=step.node_id,
        edge_from=step.edge_from,
        edge_to=step.edge_to,
        metrics=metrics,
        frontier=step.frontier,
        explored=step.explored,
        visited_order=step.visited_order,
        frontier_position=step.frontier_position,
    )


def mock_multi_location_search(
    graph,
    start_id,
    goal_ids,
    respect_goal_order=False,
):
    """Build a deterministic multi-stop demo route from real A* legs.

    In optimize mode this mock sorts goal IDs naturally. It exercises the
    multi-location UI/contract but deliberately makes no optimality claim.
    """
    goals = list(goal_ids or [])
    if graph is None or start_id not in getattr(graph, "nodes", {}):
        return SearchResult(success=False, message="Graph or start node is invalid.")
    if not goals:
        return SearchResult(success=False, message="At least one goal is required.")
    if len(set(goals)) != len(goals):
        return SearchResult(success=False, message="Goal nodes must be unique.")
    if start_id in goals:
        return SearchResult(success=False, message="Start node cannot also be a goal.")
    missing = [goal for goal in goals if goal not in graph.nodes]
    if missing:
        return SearchResult(
            success=False,
            message=f"Goal node '{missing[0]}' was not found.",
        )

    visit_order = goals if respect_goal_order else sorted(goals, key=_natural_node_key)
    leg_count = len(visit_order)
    combined_path = []
    combined_steps = []
    combined_visited = []
    total_cost = 0.0
    leg_start = start_id

    for zero_based_index, leg_goal in enumerate(visit_order):
        leg_index = zero_based_index + 1
        leg_result = a_star(graph, leg_start, leg_goal)

        for step in leg_result.steps:
            if step.step_type != StepType.FINISH:
                combined_steps.append(
                    _clone_leg_step(
                        step,
                        leg_index,
                        leg_count,
                        leg_start,
                        leg_goal,
                    )
                )

        if not leg_result.success:
            combined_steps.append(
                SearchStep(
                    StepType.FINISH,
                    node_id=leg_goal,
                    metrics={
                        "success": False,
                        "leg_index": leg_index,
                        "leg_count": leg_count,
                        "leg_start": leg_start,
                        "leg_goal": leg_goal,
                    },
                )
            )
            return SearchResult(
                path=[],
                steps=combined_steps,
                total_cost=0.0,
                success=False,
                message=f"No route exists for leg {leg_index}: {leg_start} -> {leg_goal}.",
                visited_order=combined_visited + list(leg_result.visited_order),
                goal_visit_order=visit_order,
            )

        leg_path = list(leg_result.path)
        combined_path.extend(leg_path if not combined_path else leg_path[1:])
        combined_visited.extend(leg_result.visited_order)
        total_cost += leg_result.total_cost

        leg_start = leg_goal

    combined_steps.append(
        SearchStep(
            StepType.FINISH,
            node_id=visit_order[-1],
            metrics={
                "success": True,
                "leg_count": leg_count,
                "total_cost": total_cost,
            },
        )
    )
    mode = "the selected order" if respect_goal_order else "a deterministic mock order"
    return SearchResult(
        path=combined_path,
        steps=combined_steps,
        total_cost=total_cost,
        success=True,
        message=f"Mock multi-location search visited {leg_count} goals using {mode}.",
        visited_order=combined_visited,
        goal_visit_order=visit_order,
    )
