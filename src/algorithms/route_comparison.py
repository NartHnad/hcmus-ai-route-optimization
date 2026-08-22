"""Canonical route comparison and rule-based Vietnamese explanations."""

import math
import random
import time
from dataclasses import replace
from typing import Iterable, Optional, Sequence

from src.algorithms.algorithms import run_algorithm, run_route_request
from src.constants import CongestionLevel
from src.models.models import (
    ComparisonMode,
    RouteComparison,
    RouteExplanation,
    RouteMetrics,
    RouteSegment,
)


CURRENT_COST_PROFILE = "current_composite"
HIGH_CONGESTION_THRESHOLD = CongestionLevel.HEAVY.value
METRIC_EPSILON = 1e-6


def _run_comparison_search(search, *args, **kwargs):
    """Run a secondary search without advancing the shared random stream."""
    random_state = random.getstate()
    started = time.perf_counter()
    try:
        result = search(*args, **kwargs)
        runtime_ms = (time.perf_counter() - started) * 1000
        result.runtime_ms = runtime_ms
        result.processing_time_ms = runtime_ms
        return result
    finally:
        random.setstate(random_state)


def _finite_number(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def calculate_route_metrics(
    graph,
    path: Optional[Sequence[str]],
    high_congestion_threshold: float = HIGH_CONGESTION_THRESHOLD,
    cost_mode: str = CURRENT_COST_PROFILE,
) -> RouteMetrics:
    """Calculate metrics using the current Graph and Edge semantics."""
    del cost_mode  # Kept as comparison metadata/API compatibility only.
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
        congestion = _finite_number(getattr(edge, "congestion", 0.0))
        edge_cost = _finite_number(edge.calculate_cost())
        segment = RouteSegment(
            from_node=from_node,
            to_node=to_node,
            distance=distance,
            travel_time=travel_time,
            congestion=congestion,
            congestion_penalty=congestion,
            total_cost=edge_cost,
            road_name=str(getattr(edge, "note", "") or ""),
            road_type=str(getattr(edge, "road_type", "") or ""),
            risk=_finite_number(getattr(edge, "risk", 0.0)),
        )
        segments.append(segment)
        total_distance += distance
        total_time += travel_time
        congestion_penalty += congestion
        total_cost += edge_cost

    high_congestion_segments = [
        segment
        for segment in segments
        if segment.congestion >= float(high_congestion_threshold)
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
    cost_mode: str = CURRENT_COST_PROFILE,
    route_request=None,
) -> RouteMetrics:
    """Attach comparison metrics without replacing algorithm-reported cost."""
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
    metrics.goal_visit_order = list(
        getattr(result, "goal_visit_order", []) or []
    )
    metrics.start_node = str(
        getattr(route_request, "start_node", "")
        or (metrics.path[0] if metrics.path else "")
    )
    metrics.return_to_start = bool(
        getattr(route_request, "return_to_start", False)
    )
    metrics.processing_time_ms = result.processing_time_ms
    metrics.explored_nodes = (
        None
        if getattr(route_request, "route_mode", "single") == "multi"
        else result.explored_nodes
    )
    return metrics


class _EdgeFilteredGraph:
    """Read-only graph view hiding selected edges in both traversal directions."""

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
        self.incoming_adjacency_list = {node_id: [] for node_id in graph.nodes}
        for edges in self.adjacency_list.values():
            for edge in edges:
                self.incoming_adjacency_list.setdefault(edge.to_node, []).append(edge)

    def get_node(self, node_id):
        return self._graph.get_node(node_id)

    def get_neighbors(self, node_id):
        return self.adjacency_list.get(node_id, [])

    def get_incoming_neighbors(self, node_id):
        return self.incoming_adjacency_list.get(node_id, [])

    def get_edge(self, from_node, to_node):
        for edge in self.adjacency_list.get(from_node, []):
            if edge.to_node == to_node:
                return edge
        return None

    def __getattr__(self, name):
        return getattr(self._graph, name)


class AlternativeRouteSelector:
    """Create a different route by rerunning the same registered algorithm."""

    def select(
        self,
        graph,
        selected_path: Optional[Sequence[str]],
        algorithm: str,
        route_request=None,
        cost_mode: str = CURRENT_COST_PROFILE,
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

        # Start near the end to prefer a route with a long shared prefix.
        for excluded_edge in reversed(selected_edges):
            graph_view = _EdgeFilteredGraph(graph, {excluded_edge})
            if route_request is None:
                candidate_result = _run_comparison_search(
                    run_algorithm,
                    algorithm,
                    graph_view,
                    start_id,
                    goal_id,
                )
            else:
                candidate_result = _run_comparison_search(
                    run_route_request,
                    algorithm,
                    graph_view,
                    route_request,
                )
            candidate_path = list(getattr(candidate_result, "path", []) or [])
            if (
                not getattr(candidate_result, "success", False)
                or candidate_path == selected.path
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


def _graph_has_nonnegative_costs(graph) -> Optional[bool]:
    if graph is None:
        return None
    for node_id in graph.nodes:
        for edge in graph.get_neighbors(node_id):
            cost = _finite_number(edge.calculate_cost(), float("inf"))
            if not math.isfinite(cost) or cost < 0:
                return False
    return True


def optimality_statement(
    algorithm: str,
    graph=None,
    cost_mode: str = CURRENT_COST_PROFILE,
) -> str:
    """Describe only guarantees justified by the current implementation."""
    del cost_mode
    normalized = str(algorithm or "").lower()
    if "uniform cost" in normalized or "ucs" in normalized:
        nonnegative = _graph_has_nonnegative_costs(graph)
        if nonnegative is True:
            return (
                "UCS bảo đảm tối ưu theo total cost hiện tại vì mọi chi phí cạnh "
                "trong graph đều không âm."
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
    if "a*" in normalized or "a-star" in normalized:
        return (
            "A* chỉ bảo đảm tối ưu khi heuristic admissible và consistent với "
            "total cost hiện tại; phần so sánh này không tự khẳng định các điều "
            "kiện đó cho mọi graph đầu vào."
        )
    if "genetic" in normalized or "ga" in normalized:
        return (
            "Genetic Algorithm là heuristic ngẫu nhiên và không bảo đảm nghiệm "
            "tối ưu toàn cục."
        )
    if "simulated annealing" in normalized or "(sa)" in normalized:
        return (
            "Simulated Annealing là heuristic ngẫu nhiên và không bảo đảm nghiệm "
            "tối ưu toàn cục."
        )
    if "nearest neighbor" in normalized or "2-opt" in normalized:
        return (
            "Nearest Neighbor + 2-Opt là heuristic cải thiện cục bộ và không bảo "
            "đảm nghiệm tối ưu toàn cục."
        )
    if "beam" in normalized:
        return "Beam Search cắt bớt frontier nên không bảo đảm tuyến tối ưu."
    if "bidirectional" in normalized:
        return (
            "So sánh này không khẳng định bảo đảm tối ưu cho Bidirectional Search "
            "nếu chưa kiểm chứng đầy đủ các điều kiện trọng số và dừng của graph."
        )
    return "Chưa có đủ thông tin để khẳng định thuật toán bảo đảm tối ưu."


class RouteExplanationGenerator:
    """Generate concise deterministic Vietnamese text from current metrics."""

    @staticmethod
    def _goal_order_text(order: Sequence[str]) -> str:
        return " → ".join(str(node_id) for node_id in (order or [])) or "—"

    def _visiting_order_sentence(
        self,
        mode: ComparisonMode,
        primary_algorithm: str,
        second_algorithm: str,
        selected: RouteMetrics,
        alternative: Optional[RouteMetrics],
        original_goal_order: Sequence[str],
        respect_goal_order: bool,
    ) -> str:
        supplied_order = self._goal_order_text(original_goal_order)
        first_order = self._goal_order_text(selected.goal_visit_order)
        second_order = self._goal_order_text(
            alternative.goal_visit_order if alternative is not None else []
        )

        if respect_goal_order:
            return (
                f"Yêu cầu giữ nguyên thứ tự ghé {supplied_order}; thuật toán không "
                "tối ưu lại thứ tự các điểm giao hàng."
            )
        if mode is ComparisonMode.ORIGINAL_VS_OPTIMIZED:
            if alternative is None or not alternative.valid:
                return f"Thứ tự ghé ban đầu là {supplied_order}."
            if list(selected.goal_visit_order) == list(alternative.goal_visit_order):
                return (
                    f"Thứ tự ghé ban đầu và thứ tự {primary_algorithm} tìm được "
                    f"đều là {first_order}."
                )
            return (
                f"Thứ tự ghé ban đầu là {first_order}, trong khi "
                f"{primary_algorithm} tìm được thứ tự {second_order}."
            )
        if alternative is None or not alternative.valid:
            return f"{primary_algorithm} trả về thứ tự ghé {first_order}."
        if list(selected.goal_visit_order) == list(alternative.goal_visit_order):
            return (
                f"{primary_algorithm} và {second_algorithm} cùng trả về thứ tự ghé "
                f"{first_order}."
            )
        return (
            f"{primary_algorithm} chọn thứ tự ghé {first_order}, trong khi "
            f"{second_algorithm} chọn {second_order}."
        )

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
    def _processing_time_sentence(
        first_value: float,
        second_value: float,
        first_label: str,
        second_label: str,
    ) -> str:
        """Describe only the runtime observed for this comparison execution."""
        delta = _finite_number(first_value) - _finite_number(second_value)
        if abs(delta) <= METRIC_EPSILON:
            return (
                "Trong lần chạy hiện tại, thời gian xử lý của hai tuyến gần như "
                "bằng nhau."
            )
        faster = first_label if delta < 0 else second_label
        slower = second_label if delta < 0 else first_label
        return (
            f"Trong lần chạy hiện tại, {faster} có thời gian xử lý thấp hơn "
            f"{slower} {abs(delta):.2f} ms."
        )

    @staticmethod
    def _actual_returns_to_start(metrics: Optional[RouteMetrics]) -> bool:
        if metrics is None or not metrics.valid:
            return False
        path = list(metrics.path or [])
        start_node = str(metrics.start_node or "")
        return bool(path and start_node and path[-1] == start_node)

    def _return_to_start_sentence(
        self,
        first_label: str,
        second_label: str,
        selected: RouteMetrics,
        alternative: Optional[RouteMetrics],
    ) -> str:
        first_returns = self._actual_returns_to_start(selected)
        second_returns = self._actual_returns_to_start(alternative)
        start_node = selected.start_node or (
            alternative.start_node if alternative is not None else ""
        )
        destination = f" {start_node}" if start_node else ""
        if first_returns and second_returns:
            return f"Cả hai tuyến đều quay về điểm bắt đầu{destination}."
        if first_returns:
            return (
                f"{first_label} quay về điểm bắt đầu{destination}, nhưng "
                f"{second_label} không hoàn tất yêu cầu quay về điểm bắt đầu."
            )
        if second_returns:
            return (
                f"{second_label} quay về điểm bắt đầu{destination}, nhưng "
                f"{first_label} không hoàn tất yêu cầu quay về điểm bắt đầu."
            )
        return (
            "Hai kết quả hiện tại không hoàn tất yêu cầu quay về điểm bắt đầu."
        )

    @staticmethod
    def _congestion_text(label: str, metrics: RouteMetrics) -> str:
        if not metrics.high_congestion_segments:
            return f"{label} không có đoạn ùn tắc nặng"
        segments = []
        for segment in metrics.high_congestion_segments:
            road = segment.road_name or segment.road_type
            road_text = f" ({road})" if road else ""
            segments.append(
                f"{segment.from_node} → {segment.to_node}{road_text}, mức "
                f"{segment.congestion:.2f}"
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
        cost_mode: str = CURRENT_COST_PROFILE,
        route_mode: str = "single",
        original_goal_order: Optional[Sequence[str]] = None,
        respect_goal_order: bool = False,
        return_to_start: bool = False,
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

        is_multi = str(route_mode or "single") == "multi"
        original_goal_order = list(original_goal_order or [])
        if mode is ComparisonMode.DIFFERENT_ALGORITHMS:
            first_label, second_label = "Route A", "Route B"
            intro = (
                f"Route A dùng {primary_algorithm}; Route B dùng {second_algorithm}. "
                "Hai route dùng cùng graph, yêu cầu điểm đến, dữ liệu giao thông "
                "và công thức total cost hiện tại."
            )
            missing = f"{second_algorithm} không tìm thấy Route B hợp lệ."
        elif mode is ComparisonMode.ORIGINAL_VS_OPTIMIZED:
            first_label, second_label = "Thứ tự ban đầu", "Thứ tự tối ưu hóa"
            intro = (
                f"So sánh thứ tự điểm giao hàng ban đầu với kết quả do "
                f"{primary_algorithm} tạo ra trên cùng graph, dữ liệu giao thông "
                "và công thức total cost hiện tại."
            )
            missing = f"{primary_algorithm} không tìm thấy tuyến tối ưu hóa hợp lệ."
        else:
            first_label, second_label = "Selected", "Alternative"
            intro = (
                f"Selected và Alternative đều dùng {primary_algorithm}. Alternative "
                "được chạy lại sau khi ẩn một cạnh của Selected; trọng số, dữ liệu "
                "giao thông và yêu cầu điểm đến không đổi."
            )
            missing = "Không tìm thấy Alternative hợp lệ bằng cùng thuật toán."

        if not selected.valid:
            text = (
                f"{primary_algorithm} không trả về tuyến chính hợp lệ nên chưa thể "
                f"so sánh. Về tính tối ưu: {optimality}"
            )
            return RouteExplanation(text=text, optimality_statement=optimality)

        sentences = [intro]
        if is_multi:
            sentences.append(
                self._visiting_order_sentence(
                    mode,
                    primary_algorithm,
                    second_algorithm,
                    selected,
                    alternative,
                    original_goal_order,
                    respect_goal_order,
                )
            )
            if return_to_start:
                sentences.append(
                    self._return_to_start_sentence(
                        first_label,
                        second_label,
                        selected,
                        alternative,
                    )
                )
            if mode is ComparisonMode.DIFFERENT_ALGORITHMS:
                sentences.append(
                    "Kết luận chỉ mô tả các nghiệm tìm được trong lần chạy hiện "
                    "tại, không khẳng định một thuật toán luôn vượt trội."
                )
        if alternative is None or not alternative.valid:
            sentences.extend(
                [
                    missing,
                    "Ùn tắc nặng: "
                    + self._congestion_text(first_label, selected)
                    + ".",
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
                    "Thời gian di chuyển",
                    "phút",
                    1,
                ),
                self._difference_sentence(
                    selected.total_cost,
                    alternative.total_cost,
                    first_label,
                    second_label,
                    "Total cost hiện tại",
                    "đơn vị",
                    2,
                ),
                self._difference_sentence(
                    selected.congestion_penalty,
                    alternative.congestion_penalty,
                    first_label,
                    second_label,
                    "Tổng mức ùn tắc",
                    "điểm",
                    2,
                ),
            ]
        )
        if (
            selected.processing_time_ms is not None
            and alternative.processing_time_ms is not None
        ):
            sentences.append(
                self._processing_time_sentence(
                    selected.processing_time_ms,
                    alternative.processing_time_ms,
                    first_label,
                    second_label,
                )
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
                "Ùn tắc nặng: "
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
    cost_mode: str = CURRENT_COST_PROFILE,
    route_mode: str = "single",
    original_goal_order: Optional[Sequence[str]] = None,
    respect_goal_order: bool = False,
    return_to_start: bool = False,
) -> RouteComparison:
    """Compare two routes that were measured with current graph semantics."""
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
        if (
            selected.processing_time_ms is not None
            and alternative.processing_time_ms is not None
        ):
            metric_pairs["processing_time_ms"] = (
                selected.processing_time_ms,
                alternative.processing_time_ms,
            )
        if (
            selected.explored_nodes is not None
            and alternative.explored_nodes is not None
        ):
            metric_pairs["explored_nodes"] = (
                selected.explored_nodes,
                alternative.explored_nodes,
            )
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
        route_mode=route_mode,
        original_goal_order=original_goal_order,
        respect_goal_order=respect_goal_order,
        return_to_start=return_to_start,
    )
    return RouteComparison(
        algorithm=str(algorithm or ""),
        selected=selected,
        alternative=alternative,
        mode=mode,
        comparison_algorithm=str(second_algorithm or ""),
        cost_mode=str(cost_mode or CURRENT_COST_PROFILE),
        route_mode=str(route_mode or "single"),
        original_goal_order=list(original_goal_order or []),
        respect_goal_order=bool(respect_goal_order),
        return_to_start=bool(return_to_start),
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
    cost_mode: str = CURRENT_COST_PROFILE,
    start_id: Optional[str] = None,
    goal_id: Optional[str] = None,
    route_request=None,
) -> RouteComparison:
    """Build one comparison and attach it to an existing SearchResult."""
    mode = ComparisonMode.coerce(mode)
    route_mode = str(getattr(route_request, "route_mode", "single") or "single")
    original_goal_order = list(
        getattr(route_request, "delivery_nodes", ()) or ()
    )
    respect_goal_order = bool(
        getattr(route_request, "respect_goal_order", False)
    )
    return_to_start = bool(getattr(route_request, "return_to_start", False))
    selected = enrich_search_result(
        result,
        graph,
        algorithm,
        cost_mode=cost_mode,
        route_request=route_request,
    ) 

    if mode is ComparisonMode.DIFFERENT_ALGORITHMS:
        second_algorithm = str(comparison_algorithm or "")
        
        if not second_algorithm:
            raise ValueError("A comparison algorithm is required for this mode.")
        if second_algorithm == algorithm:
            raise ValueError("Different-algorithms mode requires two algorithms.")
        if route_request is None:
            second_result = _run_comparison_search(
                run_algorithm,
                second_algorithm,
                graph,
                start_id or (selected.path[0] if selected.path else ""),
                goal_id or (selected.path[-1] if selected.path else ""),
            )
        else:
            second_result = _run_comparison_search(
                run_route_request,
                second_algorithm,
                graph,
                route_request,
            )
        alternative = enrich_search_result(
            second_result,
            graph,
            second_algorithm,
            cost_mode=cost_mode,
            route_request=route_request,
        )
    elif mode is ComparisonMode.ORIGINAL_VS_OPTIMIZED:
        if route_request is None or route_mode != "multi":
            raise ValueError(
                "Original-order comparison requires a multi-location RouteRequest."
            )
        if respect_goal_order:
            raise ValueError(
                "The current request preserves the supplied visiting order, so "
                "there is no optimized visiting order to compare."
            )
        second_algorithm = algorithm
        optimized = selected
        original_request = replace(route_request, respect_goal_order=True)
        original_result = _run_comparison_search(
            run_route_request,
            algorithm,
            graph,
            original_request,
        )
        selected = enrich_search_result(
            original_result,
            graph,
            algorithm,
            cost_mode=cost_mode,
            route_request=original_request,
        )
        alternative = optimized
    else:
        second_algorithm = algorithm
        alternative = None
        if selected.valid:
            alternative = AlternativeRouteSelector().select(
                graph,
                selected.path,
                algorithm,
                route_request=route_request,
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
        route_mode=route_mode,
        original_goal_order=original_goal_order,
        respect_goal_order=respect_goal_order,
        return_to_start=return_to_start,
    )
    result.comparison = comparison
    return comparison
