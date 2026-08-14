"""Shared, renderer-safe route selection payload helpers."""


def normalize_route_selection(start, goals, display_order=None, preview_goal=None):
    """Return the canonical selection payload consumed by both renderers.

    ``display_order=[]`` is meaningful and therefore must not fall back to
    ``goals``. Unknown IDs and duplicates are removed. Renderers retain their
    existing fallback that assigns any omitted goal a marker label.
    """
    selected_goals = list(goals or [])
    requested_order = (
        list(selected_goals)
        if display_order is None
        else list(display_order)
    )
    selected = set(selected_goals)
    normalized_order = []
    for goal_id in requested_order:
        if goal_id in selected and goal_id not in normalized_order:
            normalized_order.append(goal_id)
    return {
        "start": start or None,
        "goals": selected_goals,
        "display_order": normalized_order,
        "preview_goal": preview_goal or None,
    }
