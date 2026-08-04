"""Canonical route comparison and rule-based Vietnamese explanations."""

import math
from typing import Iterable, Optional, Sequence

from src.algorithms.algorithms import run_algorithm
from src.models.models import (
    ComparisonMode,
    RouteComparison,
    RouteExplanation,
    RouteMetrics,
    RouteSegment,
)


CANONICAL_COST_MODE = "optimal"
HIGH_CONGESTION_THRESHOLD = 4
METRIC_EPSILON = 1e-6


def _finite_number(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def calculate_route_metrics(
    graph,
    path: Optional[Sequence[str]],
    high_congestion_threshold: int = HIGH_CONGESTION_THRESHOLD,
    cost_mode: str = CANONICAL_COST_MODE,
) -> RouteMetrics:
    """Calculate one canonical metric set for every route and algorithm."""
    normalized_path = list(path or [])
    if graph is None or not normalized_path:
        return RouteMetrics(path=normalized_path, valid=False)
    if any(node_id not in graph.nodes for node_id in normalized_path):
        return RouteMetrics(path=normalized_path, valid=False)

    segments = []
    total_distance = 0.0
    total_time = 0.0
    congestion_penalty = 0.0
    total_cost = 0.0

    for from_node, to_node in zip(normalized_path, normalized_path[1:]):
        edge = graph.get_edge(from_node, to_node)
        if edge is None:
            return RouteMetrics(path=normalized_path, valid=False)

        distance = _finite_number(edge.distance)
        travel_time = _finite_number(edge.travel_time)
        congestion = int(getattr(edge, "congestion", 0) or 0)
        edge_congestion_penalty = _finite_number(congestion)
        edge_cost = _finite_number(edge.calculate_cost(mode=cost_mode))
        segment = RouteSegment(
            from_node=from_node,
            to_node=to_node,
            distance=distance,
            travel_time=travel_time,
            congestion=congestion,
            congestion_penalty=edge_congestion_penalty,
            total_cost=edge_cost,
            road_name=str(getattr(edge, "note", "") or ""),
            road_type=str(getattr(edge, "road_type", "") or ""),
            risk=int(getattr(edge, "risk", 0) or 0),
        )
        segments.append(segment)
        total_distance += distance
        total_time += travel_time
        congestion_penalty += edge_congestion_penalty
        total_cost += edge_cost

    high_congestion_segments = [
        segment
        for segment in segments
        if segment.congestion >= int(high_congestion_threshold)
    ]
    return RouteMetrics(
        path=normalized_path,
        segments=segments,
        total_distance=_finite_number(total_distance),
        total_time=_finite_number(total_time),
        congestion_penalty=_finite_number(congestion_penalty),
        total_cost=_finite_number(total_cost),
        high_congestion_segments=high_congestion_segments,
        valid=True,
    )


def _max_frontier_size(steps: Iterable, start_id: Optional[str]) -> int:
    """Reconstruct a bounded frontier count from snapshot or delta events."""
    frontier = [start_id] if start_id else []
    maximum = len(frontier)

    for raw_step in steps or []:
        step = raw_step.to_dict() if hasattr(raw_step, "to_dict") else dict(raw_step)
        snapshot = step.get("frontier")
        if snapshot is not None:
            frontier = list(snapshot)
        else:
            node_id = step.get("node")
            step_type = step.get("type")
            if step_type == "expand" and node_id in frontier:
                frontier.remove(node_id)
            elif step_type in {"discover", "update"} and node_id:
                if node_id not in frontier:
                    frontier.append(node_id)
        maximum = max(maximum, len(frontier))
    return maximum


def enrich_search_result(
    result,
    graph,
    algorithm: str,
    cost_mode: str = CANONICAL_COST_MODE,
) -> RouteMetrics:
    """Attach canonical metrics without replacing algorithm-reported cost."""
    metrics = calculate_route_metrics(
        graph,
        getattr(result, "path", []),
        cost_mode=cost_mode,
    )
    result.algorithm = str(algorithm or "")
    result.segments = list(metrics.segments)
    result.total_distance = metrics.total_distance if metrics.valid else None
    result.total_time = metrics.total_time if metrics.valid else None
    result.estimated_time = metrics.total_time if metrics.valid else None
    result.congestion_penalty = (
        metrics.congestion_penalty if metrics.valid else None
    )
    result.explored_nodes = len(getattr(result, "visited_order", []) or [])
    result.processing_time_ms = _finite_number(getattr(result, "runtime_ms", 0.0))
    result.max_frontier_size = _max_frontier_size(
        getattr(result, "steps", []),
        metrics.path[0] if metrics.path else None,
    )
    result.route_details = [segment.to_dict() for segment in metrics.segments]
    return metrics


class _EdgeFilteredGraph:
    """Read-only graph view that hides edges but reuses all source traffic data."""

    def __init__(self, graph, excluded_edges):
        self._graph = graph
        self.nodes = graph.nodes
        excluded = set(excluded_edges)
        self.adjacency_list = {
            node_id: [
                edge
                for edge in graph.get_neighbors(node_id)
                if (edge.from_node, edge.to_node) not in excluded
            ]
            for node_id in graph.nodes
        }

    def get_node(self, node_id):
        return self._graph.get_node(node_id)

    def get_neighbors(self, node_id):
        return self.adjacency_list.get(node_id, [])

    def get_edge(self, from_node, to_node):
        for edge in self.adjacency_list.get(from_node, []):
            if edge.to_node == to_node:
                return edge
        return None

    def __getattr__(self, name):
        return getattr(self._graph, name)


class AlternativeRouteSelector:
    """Create a different route by rerunning the same public algorithm."""

    def select(
        self,
        graph,
        selected_path: Optional[Sequence[str]],
        algorithm: str,
        cost_mode: str = CANONICAL_COST_MODE,
    ) -> Optional[RouteMetrics]:
        selected = calculate_route_metrics(
            graph,
            selected_path,
            cost_mode=cost_mode,
        )
        if not selected.valid or len(selected.path) < 2:
            return None

        start_id = selected.path[0]
        goal_id = selected.path[-1]
        selected_edges = list(zip(selected.path, selected.path[1:]))

        # Start near the goal to prefer a comparable route with a long shared prefix.
        for excluded_edge in reversed(selected_edges):
            graph_view = _EdgeFilteredGraph(graph, {excluded_edge})
            candidate_result = run_algorithm(
                algorithm,
                graph_view,
                start_id,
                goal_id,
            )
            candidate_path = list(getattr(candidate_result, "path", []) or [])
            if (
                not getattr(candidate_result, "success", False)
                or candidate_path == selected.path
                or len(candidate_path) != len(set(candidate_path))
            ):
                continue

            candidate = calculate_route_metrics(
                graph,
                candidate_path,
                cost_mode=cost_mode,
            )
            if candidate.valid:
                return candidate
        return None


def _winner(first_value, second_value, epsilon=METRIC_EPSILON):
    delta = _finite_number(first_value) - _finite_number(second_value)
    if abs(delta) <= epsilon:
        return "tie"
    return "selected" if delta < 0 else "alternative"


def _graph_has_nonnegative_costs(graph, cost_mode: str) -> Optional[bool]:
    if graph is None:
        return None
    for node_id in graph.nodes:
        for edge in graph.get_neighbors(node_id):
            cost = _finite_number(edge.calculate_cost(mode=cost_mode), float("inf"))
            if not math.isfinite(cost) or cost < 0:
                return False
    return True


def optimality_statement(
    algorithm: str,
    graph=None,
    cost_mode: str = CANONICAL_COST_MODE,
) -> str:
    """Describe only guarantees justified by the current implementation."""
    normalized = str(algorithm or "").lower()
    if "uniform cost" in normalized or "ucs" in normalized:
        nonnegative = _graph_has_nonnegative_costs(graph, cost_mode)
        if nonnegative is True:
            return (
                "UCS bảo đảm tối ưu theo total cost chuẩn hóa vì mọi chi phí cạnh "
                "trong graph hiện tại đều không âm."
            )
        if nonnegative is False:
            return (
                "UCS không được bảo đảm tối ưu vì graph có chi phí cạnh âm hoặc "
                "không hợp lệ."
            )
        return "UCS chỉ bảo đảm tối ưu khi mọi chi phí cạnh đều không âm."
    if "breadth-first" in normalized or "bfs" in normalized:
        return (
            "BFS bảo đảm ít cạnh nhất trong graph không trọng số, nhưng không bảo "
            "đảm tốt nhất theo khoảng cách, thời gian hoặc total cost hiện tại."
        )
    if "depth-first" in normalized or "dfs" in normalized:
        return "DFS không bảo đảm tuyến tìm được là tuyến tối ưu."
    if "genetic" in normalized or "ga" in normalized:
        return (
            "Genetic Algorithm là heuristic ngẫu nhiên và không bảo đảm nghiệm "
            "tối ưu toàn cục."
        )
    if "a*" in normalized or "a-star" in normalized:
        return (
            "A* chỉ bảo đảm tối ưu khi heuristic admissible/consistent với cost "
            "đang tối ưu; heuristic khoảng cách hiện tại chưa chứng minh điều đó "
            "cho total cost tổng hợp."
        )
    return "Chưa có đủ thông tin để khẳng định thuật toán bảo đảm tối ưu."


class RouteExplanationGenerator:
    """Generate concise deterministic Vietnamese text from canonical metrics."""

    @staticmethod
    def _difference_sentence(
        first_value: float,
        second_value: float,
        first_label: str,
        second_label: str,
        metric_label: str,
        unit: str,
        decimals: int,
    ) -> str:
        delta = _finite_number(first_value) - _finite_number(second_value)
        if abs(delta) <= METRIC_EPSILON:
            return f"{metric_label}: hai tuyến gần như bằng nhau."
        winner = first_label if delta < 0 else second_label
        return (
            f"{metric_label}: {winner} tốt hơn {abs(delta):.{decimals}f} {unit}."
        )

    @staticmethod
    def _congestion_text(label: str, metrics: RouteMetrics) -> str:
        if not metrics.high_congestion_segments:
            return f"{label} không có đoạn ùn tắc cao"
        segments = []
        for segment in metrics.high_congestion_segments:
            road = segment.road_name or segment.road_type
            road_text = f" ({road})" if road else ""
            segments.append(
                f"{segment.from_node} → {segment.to_node}{road_text}, mức "
                f"{segment.congestion}"
            )
        return f"{label}: " + "; ".join(segments)

    def generate(
        self,
        mode,
        primary_algorithm: str,
        comparison_algorithm: str,
        selected: RouteMetrics,
        alternative: Optional[RouteMetrics],
        graph=None,
        cost_mode: str = CANONICAL_COST_MODE,
    ) -> RouteExplanation:
        mode = ComparisonMode.coerce(mode)
        second_algorithm = comparison_algorithm or primary_algorithm
        optimality_parts = [
            f"{primary_algorithm}: "
            + optimality_statement(primary_algorithm, graph, cost_mode)
        ]
        if second_algorithm != primary_algorithm:
            optimality_parts.append(
                f"{second_algorithm}: "
                + optimality_statement(second_algorithm, graph, cost_mode)
            )
        optimality = " ".join(optimality_parts)

        if mode is ComparisonMode.DIFFERENT_ALGORITHMS:
            first_label, second_label = "Route A", "Route B"
            intro = (
                f"Route A dùng {primary_algorithm}; Route B dùng {second_algorithm}. "
                "Hai route dùng cùng graph, start, goal, traffic và cost chuẩn hóa."
            )
            missing = f"{second_algorithm} không tìm thấy Route B hợp lệ."
        else:
            first_label, second_label = "Selected", "Alternative"
            intro = (
                f"Selected và Alternative đều dùng {primary_algorithm}. Alternative "
                "được chạy lại với ràng buộc loại một cạnh của Selected để buộc "
                "tuyến khác; trọng số và traffic không đổi."
            )
            missing = "Không tìm thấy Alternative hợp lệ bằng cùng thuật toán."

        if not selected.valid:
            text = (
                f"{primary_algorithm} không trả về tuyến chính hợp lệ nên chưa thể "
                f"so sánh. Về tính tối ưu: {optimality}"
            )
            return RouteExplanation(text=text, optimality_statement=optimality)

        sentences = [intro]
        if alternative is None or not alternative.valid:
            sentences.extend(
                [
                    missing,
                    "Ùn tắc cao: " + self._congestion_text(first_label, selected) + ".",
                    "Về tính tối ưu: " + optimality,
                ]
            )
            return RouteExplanation(
                text=" ".join(sentences),
                optimality_statement=optimality,
            )

        sentences.extend(
            [
                self._difference_sentence(
                    selected.total_distance,
                    alternative.total_distance,
                    first_label,
                    second_label,
                    "Khoảng cách",
                    "km",
                    2,
                ),
                self._difference_sentence(
                    selected.total_time,
                    alternative.total_time,
                    first_label,
                    second_label,
                    "Thời gian",
                    "phút",
                    1,
                ),
                self._difference_sentence(
                    selected.total_cost,
                    alternative.total_cost,
                    first_label,
                    second_label,
                    "Total cost",
                    "đơn vị",
                    2,
                ),
                self._difference_sentence(
                    selected.congestion_penalty,
                    alternative.congestion_penalty,
                    first_label,
                    second_label,
                    "Phạt ùn tắc",
                    "điểm",
                    1,
                ),
            ]
        )
        cost_winner = _winner(selected.total_cost, alternative.total_cost)
        if cost_winner == "tie":
            sentences.append("Gợi ý theo total cost: hai route tương đương.")
        else:
            recommended = first_label if cost_winner == "selected" else second_label
            recommended_algorithm = (
                primary_algorithm
                if cost_winner == "selected"
                else second_algorithm
            )
            sentences.append(
                f"Gợi ý theo total cost: chọn {recommended} ({recommended_algorithm})."
            )
        sentences.extend(
            [
                "Ùn tắc cao: "
                + self._congestion_text(first_label, selected)
                + "; "
                + self._congestion_text(second_label, alternative)
                + ".",
                "Về tính tối ưu: " + optimality,
            ]
        )
        return RouteExplanation(
            text=" ".join(sentences),
            optimality_statement=optimality,
        )


def compare_routes(
    selected: RouteMetrics,
    alternative: Optional[RouteMetrics],
    algorithm: str,
    mode=ComparisonMode.SAME_ALGORITHM_ALTERNATIVE,
    comparison_algorithm: Optional[str] = None,
    graph=None,
    cost_mode: str = CANONICAL_COST_MODE,
) -> RouteComparison:
    """Compare two already-normalized routes without algorithm-specific logic."""
    mode = ComparisonMode.coerce(mode)
    second_algorithm = comparison_algorithm or algorithm
    winners = {}
    differences = {}
    if selected.valid and alternative is not None and alternative.valid:
        metric_pairs = {
            "distance": (selected.total_distance, alternative.total_distance),
            "time": (selected.total_time, alternative.total_time),
            "congestion_penalty": (
                selected.congestion_penalty,
                alternative.congestion_penalty,
            ),
            "total_cost": (selected.total_cost, alternative.total_cost),
        }
        for metric_name, (first_value, second_value) in metric_pairs.items():
            winners[metric_name] = _winner(first_value, second_value)
            differences[metric_name] = _finite_number(first_value - second_value)

    explanation = RouteExplanationGenerator().generate(
        mode,
        algorithm,
        second_algorithm,
        selected,
        alternative,
        graph=graph,
        cost_mode=cost_mode,
    )
    return RouteComparison(
        algorithm=str(algorithm or ""),
        selected=selected,
        alternative=alternative,
        mode=mode,
        comparison_algorithm=str(second_algorithm or ""),
        cost_mode=str(cost_mode or CANONICAL_COST_MODE),
        winners=winners,
        differences=differences,
        explanation=explanation,
    )


def build_route_comparison(
    graph,
    result,
    algorithm: str,
    mode=ComparisonMode.SAME_ALGORITHM_ALTERNATIVE,
    comparison_algorithm: Optional[str] = None,
    cost_mode: str = CANONICAL_COST_MODE,
    start_id: Optional[str] = None,
    goal_id: Optional[str] = None,
) -> RouteComparison:
    """Build one mode-specific comparison and attach it to SearchResult."""
    mode = ComparisonMode.coerce(mode)
    selected = enrich_search_result(result, graph, algorithm, cost_mode=cost_mode)

    if mode is ComparisonMode.DIFFERENT_ALGORITHMS:
        second_algorithm = str(comparison_algorithm or "")
        if not second_algorithm:
            raise ValueError("A comparison algorithm is required for this mode.")
        if second_algorithm == algorithm:
            raise ValueError("Different-algorithms mode requires two algorithms.")
        second_result = run_algorithm(
            second_algorithm,
            graph,
            start_id or (selected.path[0] if selected.path else ""),
            goal_id or (selected.path[-1] if selected.path else ""),
        )
        alternative = enrich_search_result(
            second_result,
            graph,
            second_algorithm,
            cost_mode=cost_mode,
        )
    else:
        second_algorithm = algorithm
        alternative = None
        if selected.valid:
            alternative = AlternativeRouteSelector().select(
                graph,
                selected.path,
                algorithm,
                cost_mode=cost_mode,
            )

    comparison = compare_routes(
        selected,
        alternative,
        algorithm,
        mode=mode,
        comparison_algorithm=second_algorithm,
        graph=graph,
        cost_mode=cost_mode,
    )
    result.comparison = comparison
    return comparison
