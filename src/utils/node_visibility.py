import re


# #NhatHuyChanged: central rules for hiding nodes without real names.
HIDDEN_NAME_KINDS = {
    "missing_data",
    "no_data",
    "unnamed_road",
}

HIDDEN_NAME_MARKERS = (
    "không có",
    "khong co",
    "chưa có",
    "chua co",
    "unknown",
    "no data",
    "unnamed",
)

GENERIC_NODE_NAME_RE = re.compile(r"node\s+\S+(\s+\[.*\])?", re.IGNORECASE)


def is_visible_node(node) -> bool:
    """Return True when a node has a real displayable place/road name."""
    # #NhatHuyChanged: hide empty/generic/unknown/unnamed node labels.
    name = str(getattr(node, "name", "") or "").strip()
    name_kind = str(getattr(node, "name_kind", "") or "").strip().casefold()

    if not name:
        return False

    if name_kind in HIDDEN_NAME_KINDS:
        return False

    if GENERIC_NODE_NAME_RE.fullmatch(name):
        return False

    normalized_name = name.casefold()
    return not any(marker in normalized_name for marker in HIDDEN_NAME_MARKERS)
