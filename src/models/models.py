# src/models.py

from src.constants import (
    DEFAULT_ALPHA,
    DEFAULT_BETA,
    DEFAULT_DELTA,
    DEFAULT_GAMMA,
    StepType,
)
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from src.constants import StepType


@dataclass(frozen=True) # sau khi tạo thì không thể gán lại thuộc tính,  giúp 1 yêu cầu không bị thay đổi trong lúc chạy thuật toán
class RouteRequest: # lưu yêu cầu tìm đường
    """An immutable snapshot of the locations selected for a route search."""

    start_node: str # điểm xuất phát
    delivery_nodes: tuple[str, ...] # các điểm cần đi tới
    respect_goal_order: bool = False # có giữ đúng thử tự điểm giao hàng hay không
    return_to_start: bool = False # có quay về điểm xuất phát hay không

    @property
    def route_mode(self) -> str:
        """Return the algorithm registry mode required by this request."""
        """Từ hai điểm giao hàng trở lên thì trả về multi, còn không hoặc 1 điểm thì trả về single"""
        return "multi" if len(self.delivery_nodes) >= 2 else "single"


class Node:
    """
    Represents a physical traffic intersection, landmark, school, hospital, bus station, warehouse, or district.
    It stores coordinates (lat, lon)
    and computing Heuristic distances (e.g., Euclidean) for informed search algorithms like A* and Greedy BFS.
    """

    def __init__(
        self,
        node_id: str,
        name: str,
        lat: float,
        lon: float,
        node_type: str = "intersection",
    ):
        self.id = node_id
        self.name = name

        self.lat = lat  # latitude: Vi do
        self.lon = lon  # longitude: Kinh do
        self.node_type = node_type  # Giao lộ, Bệnh viện, ...

    # Magic Method: define how a Node object is represented as a string
    def __repr__(self): # tạo chuỗi ngắn để debug
        return f"Node({self.id}, {self.name})"


class Edge:
    """
    Represents a directed urban street segment connecting two intersection.
    """

    def __init__(
        self,
        from_node: str, # hai đầu đoạn đường
        to_node: str,
        distance: float, # khoảng cách km
        travel_time: float, # thời gian (phút)
        road_type: str, # loại đường
        is_one_way: bool = False, # đường 1 chiều hay 2 chiều
        congestion: float = 0.0, # mức tắc đường, trong khoảng 0-1
        risk: float = 0.0, # mức rủi ro, tronng khoảng 0-1
        note: str = "", # ghi chú hoặc tên đường
    ):
        self.from_node = from_node
        self.to_node = to_node

        # Compulsory Attributes
        self.distance = float(distance)  # Raw physical distance (kilometers)
        self.travel_time = float(travel_time)  # Current estimated travel time (minutes)
        self._base_travel_time = self.travel_time  # Thời gian đi qua đoạn đường khi chưa bị ảnh hưởng của ùn tắc
        """
        Nhờ giữ _base_travel_time, khi congestion trở về 0, thời gian cũng trở lại đúng 10 phút, thay vì tiếp tục tính chồng lên thời gian đã tăng trước đó.
        """
        self.road_type = road_type
        self.is_one_way = is_one_way  # Traffic direction: 'one-way' or 'two-way'

        # Normalized Values 0.0 -> 1.0
        self.norm_distance = 0.0
        self.norm_travel_time = 0.0

        # Traffic traffic level scaled from a to b
        self.congestion = float(congestion)  # 0.0 -> 1.0
        # Penalty for flooding, construction, difficult intersections, narrow roads, or unsafe areas
        self.risk = float(risk)  # 0.0 -> 1.0
        self.note = note

        # Cached Cost Value
        self.weight = 0.0 
        """
        Bản lưu sẵn chi phí tổng hợp của cạnh
        weight = 0.25 × khoảng cách chuẩn hóa + 0.45 × thời gian chuẩn hóa + 0.20 × mức tắc đường + 0.10 × mức rủi ro
        
        Ban đầu là 0.0
        Sau khi graph_factory chuẩn hóa dữ liệu, nó mới tính
        edge.weight = edge.calculate_cost()
        
        Sau khi giao thôgn thay đổi, graph_updater.py()
        nó cũng được tính: edge.weight = edge.calculate_cost()
        """

    def calculate_cost(
        self,
        alpha: float = DEFAULT_ALPHA,
        beta: float = DEFAULT_BETA,
        gamma: float = DEFAULT_GAMMA,
        delta: float = DEFAULT_DELTA,
    ) -> float:
        """
        Dynamically evaluate the edge's weight based on different routing strategies.

        Cost = alpha * Distance + beta * Time + gamma * Congestion + delta * Risk
        Cost = 0.25 * Distance_norm + 0.45 * Time_norm + 0.2 * Congestion + 0.1 * Risk

        Mode:
        Shortest Distance
        Fastest Route
        Safest Route
        Optimal Route
        """
        # Lightweight/test graphs may be assembled directly without the
        # factory's normalization pass. Preserve the legacy raw-cost fallback
        # for those graphs while loaded datasets continue to use the weighted
        # normalized formula below.
        if self.norm_distance == 0.0 and self.norm_travel_time == 0.0:
            """
            Nếu cả norm_distance và norm_travel_time đều bằng 0, hàm coi đây là đồ thị đơn giản chưa qua grpah_factory và dùng công thức dự phòng 
            """
            return self.distance + self.travel_time

        return (
            (alpha * self.norm_distance)
            + (beta * self.norm_travel_time)
            + (gamma * self.congestion)
            + (delta * self.risk)
        )

    def reversed(self): # tạo 1 cạnh ngược chiều
        """Return a reversed copy of this edge for legacy two-way graph building."""
        if self.is_one_way: # nếu đó là đường 1 chiều thì từ chối
            raise ValueError(
                f"Cannot reverse one-way edge: " f"{self.from_node} -> {self.to_node}"
            )

        rev_edge = Edge(
            from_node=self.to_node, # đổi chiều
            to_node=self.from_node, # đổi chiều 
            distance=self.distance,
            travel_time=self.travel_time, 
            road_type=self.road_type,
            is_one_way=False, # không phải là đường 1 chiều
            congestion=self.congestion,
            risk=self.risk,
            note=self.note,
        )

        rev_edge.norm_distance = self.norm_distance
        rev_edge.norm_travel_time = self.norm_travel_time
        rev_edge.weight = self.weight

        return rev_edge

    def __repr__(self): # tạo chuỗi debug
        return f"Edge({self.from_node} -> {self.to_node}, cost={self.calculate_cost()})"


def _finite_float(value, default=0.0): # chuẩn háo 1 giá trị thành số thực hữu hạn
    """
    Chuyển được sang float và hữu hạn: trả về số đó.
    None, chuỗi không hợp lệ: trả default.
    NaN, +inf, -inf: trả default.
    """
    """Return a finite float so route-comparison payloads stay JSON-safe."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if math.isfinite(number) else float(default)


@dataclass
class RouteSegment: 
    """
        Chứa số liệu của 1 đoạn trong tuyến đường, là bản ghi chi tiết của một đônạ đường thực sự được chọn trong kết quả

        Ví dụ thuật toán tìm đựo đường A -> B -> C
        Tuyến này gồm 2 route segment:
        RouteSegment 1: A → B
        RouteSegment 2: B → C

    Ví dụ graph có
    A → B
    A → D
    B → C
    D → C

    Thuật táon chọn A -> B -> C
    Khi đó chỉ hai đoạn A → B và B → C được chuyển thành RouteSegment. Các cạnh A → D, D → C vẫn là Edge trong graph nhưng không thuộc kết quả.
    
    Sau khi thuậ toán đã tìm ra được path, calculate_route_metrics() sẽ duyệt từng cặp node liên tiếp
    Từ đó tạo ra 2 route segment
    Tại sao không chỉ lưu path ?
    
    Path chỉ chứa các id node, nó không biết đoạn đường nào đang tắc, mỗi đoạn dài bao nhiêu,... Route segment bổ sung những thông tin này
    
    Sau đó GUI có thể hiển thị lên
    Tuyến A có 1 đoạn ùn tắc nặng:
    B → C, đường Nguyễn Văn Cừ, congestion = 0.8
    """

    """Current-project metrics for one directed edge in a route."""

    from_node: str
    to_node: str
    distance: float
    travel_time: float
    congestion: float
    congestion_penalty: float
    total_cost: float
    road_name: str = ""
    road_type: str = ""
    risk: float = 0.0

    def to_dict(self):
        return {
            "from": self.from_node,
            "to": self.to_node,
            "distance": _finite_float(self.distance),
            "travel_time": _finite_float(self.travel_time),
            "congestion": _finite_float(self.congestion),
            "congestion_penalty": _finite_float(self.congestion_penalty),
            "total_cost": _finite_float(self.total_cost),
            "road": self.road_name or self.road_type or "Unknown road",
            "road_name": self.road_name or "",
            "road_type": self.road_type or "",
            "risk": _finite_float(self.risk),
        }


@dataclass
class RouteMetrics:
    """Algorithm-independent measurements computed from the current graph."""

    """
    Tổng hợp số liệu của một tuyến
    - Đường đi và các segment
    - Tổng khoảng cách, thời gian, chi phí.
    - Các đoạn tắc nghẽn cao.
    - Thứ tự ghé điểm giao hàng.
    - Thời gian xử lý và số node đã duyệt.
    - Tuyến có hợp lệ hay không.
    """

    """
    RouteMetrics(
    path=["A", "B", "C"],
    segments=[
        RouteSegment(from_node="A", to_node="B", ...),
        RouteSegment(from_node="B", to_node="C", ...),
    ],
    total_distance=5.0,
    total_time=13.0,
    congestion_penalty=1.0,
    total_cost=0.8,
    valid=True,
    )
    """

    path: List[str] = field(default_factory=list)
    segments: List[RouteSegment] = field(default_factory=list)
    total_distance: float = 0.0
    total_time: float = 0.0
    congestion_penalty: float = 0.0 # tổng mức phạt tắc nghẽn (congestion_penalty += segment.congestion, chưa nhân với trọng số gamma)
    total_cost: float = 0.0 # được tính từ edge.calculate_cost()
    high_congestion_segments: List[RouteSegment] = field(
        default_factory=list
    )  # danh sách các đoạn có mức tắc nghẽn cao, GUI dùng danh sách này để báo đoạn nào đang tắc nặng.
    valid: bool = False # cho biết tuyến này có hợp lệ hay không (true khi có path, mọi node trong path đều tồn tại, giữa mọi cặp node liên tiếp đều có edge)
    goal_visit_order: List[str] = field(default_factory=list) # Chỉ chứa điểm giao hàng
    start_node: str = ""
    return_to_start: bool = False # cho biết yêu cầu tìm đường có chế độ quay lại điểm xuất phát không
    processing_time_ms: Optional[float] = None # thời gian thuật toán xử lý, tính bằng ms
    explored_nodes: Optional[int] = None # số node mà thuật toán đã lấy để mở rộng

    def to_dict(self):
        return {
            "valid": bool(self.valid),
            "path": list(self.path),
            "goal_visit_order": list(self.goal_visit_order),
            "start_node": str(self.start_node or ""),
            "return_to_start": bool(self.return_to_start),
            "segments": [segment.to_dict() for segment in self.segments],
            "total_distance": _finite_float(self.total_distance),
            "total_time": _finite_float(self.total_time),
            "congestion_penalty": _finite_float(self.congestion_penalty),
            "total_cost": _finite_float(self.total_cost),
            "processing_time_ms": (
                None
                if self.processing_time_ms is None
                else _finite_float(self.processing_time_ms)
            ),
            "explored_nodes": (
                None
                if self.explored_nodes is None
                else max(0, int(self.explored_nodes))
            ),
            "high_congestion_segments": [
                segment.to_dict() for segment in self.high_congestion_segments
            ],
        }


@dataclass
class RouteExplanation:
    """Deterministic Vietnamese comparison text and optimality caveat."""
    """
    Dùng để chứa phần giải thích ngôn ngữ tự nhiên sau khi chương trình so sánh 2 tuyến đường
    Nó không tự tính toán tuyến đường và cũng không tự tạo nội dung. Nội dung được RouteExplanationGenerator tạo rồi đặt vào object này.
    """

    text: str = ""
    optimality_statement: str = ""

    def to_dict(self):
        return {
            "text": str(self.text or ""),
            """
            # nnooij sung giải thích của phép so sánh, hai tuyến sử dụng thuật toán nào, tuyến nào ngắn hơn
            Hai tuyến sử dụng thuật toán nào.
            Tuyến nào ngắn hơn.
            Tuyến nào nhanh hơn.
            Tuyến nào có total cost thấp hơn.
            Tuyến nào bị tắc đường nhiều hơn.
            Tuyến nào được đề xuất.
            Thứ tự ghé điểm giao hàng.
            """
            "optimality_statement": str(self.optimality_statement or ""), # nhận xét riêng về việc thuật táon có đảm bảo tối ưu koong, nó được tách khỏi text để GUI có thể hiển thi một vùng riêng
        }
    """
    explanation = RouteExplanation(
    text="Route A ngắn hơn Route B 2.5 km.",
    optimality_statement="UCS bảo đảm tối ưu vì mọi cạnh có chi phí không âm.",)
    """


class ComparisonMode(Enum):
    """Supported ways to obtain the second route in a comparison."""

    DIFFERENT_ALGORITHMS = "different_algorithms"
    SAME_ALGORITHM_ALTERNATIVE = "same_algorithm_alternative"
    ORIGINAL_VS_OPTIMIZED = "original_vs_optimized"

    # dùng để giới hạn cách chương trình tạo tuyến thứ 2 khi so sánh
    # So sánh thuậ ttoans khác trên cùng 1 yêu cầu
    # Dùng cùng 1 thuật toán để tìm một tuyến thay thế
    # So sánh thứ tự giao hàng người dùg nhập với thứ tự được thuật toán tối ưu hóa
    @classmethod
    def coerce(cls, value):
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value))
        except ValueError as exc:
            raise ValueError(f"Unsupported comparison mode: {value}") from exc


@dataclass
class RouteComparison:
    """Metrics and explanation for two routes evaluated on one graph state."""

    # Dùng để chứa toàn bộ kết quả so sánh giữa 2 tuyến đường

    """
    Nó không trực tiếp chạy thuật toán hay tính toán. Các hàm trong route_comparison.py thực hiện việc đó rồi đóng gói kết quả vào RouteComparison.
    """

    algorithm: str # tên thuật toán tạo ra tuyến chính selected
    selected: RouteMetrics # số liệu của tuyến chính
    alternative: Optional[RouteMetrics] = None # Số liệu của tuyến thứ 2 
    mode: ComparisonMode = ComparisonMode.SAME_ALGORITHM_ALTERNATIVE
    comparison_algorithm: str = "" # tên thuật toán tạo tuyến thứ 2
    cost_mode: str = "current_composite" # tên chế độ tính chi phí khi đánh giá 2 tuyến 
    """
    0.25 × norm_distance + 0.45 × norm_travel_time + 0.20 × congestion + 0.10 × risk
    """
    winners: Dict[str, str] = field(default_factory=dict)
    """
    Cho biết tuyến nào thắng theo từng tiêu chí
    
    winners = {
    "distance": "selected",
    "time": "alternative",
    "congestion_penalty": "tie",
    "total_cost": "alternative",
    }
    """
    differences: Dict[str, float] = field(default_factory=dict) # lưu độ chênh lệch giữa tuyến chính và tuyến thứ 2
    explanation: RouteExplanation = field     (default_factory=RouteExplanation) # Chứa phần giải thích bằng tiếng việt
    route_mode: str = "single" # cho biết đây là bài toán single hay multi
    original_goal_order: List[str] = field(default_factory=list) # thứ tự điểm giao hàng mà người dùng nhập ban đầu
    respect_goal_order: bool = False #cho biết thuật toán có bắt buộc giữ nguyên thứ tự người dùng nhập không, False để được phép thay đổi để giảm cost
    return_to_start: bool = False

    def to_dict(self):
        mode = ComparisonMode.coerce(self.mode)
        alternative = (
            self.alternative.to_dict() if self.alternative is not None else None
        )
        return {
            "mode": mode.value,
            "algorithm": str(self.algorithm or ""),
            "primary_algorithm": str(self.algorithm or ""),
            "comparison_algorithm": str(
                self.comparison_algorithm or self.algorithm or ""
            ),
            "cost_mode": str(self.cost_mode or "current_composite"),
            "route_mode": str(self.route_mode or "single"),
            "original_goal_order": list(self.original_goal_order),
            "respect_goal_order": bool(self.respect_goal_order),
            "return_to_start": bool(self.return_to_start),
            "selected": self.selected.to_dict(),
            "alternative": alternative,
            "route_a": self.selected.to_dict(),
            "route_b": alternative,
            "winners": dict(self.winners),
            "differences": {
                key: _finite_float(value)
                for key, value in self.differences.items()
            },
            "explanation": self.explanation.to_dict(),
        }


class SearchStep:
    """
    Represents a single search event emitted in chronological order.

    Algorithm → GUI contract:
    - EXPAND: Node removed from frontier for expansion.
    - DISCOVER: First time a node is found and added to frontier.
    - UPDATE: Better path to an existing node is found.
    - FINISH: Search terminates (success or failure).

    Rules:
    - Emit exactly one SearchStep when the event occurs.
    - Do not batch or reconstruct events afterward.
    - Unused fields must be None.

    ``frontier``/``explored``/``visited_order`` remain supported for small,
    legacy producers. Core graph-search algorithms emit compact delta events
    instead: DISCOVER/UPDATE adds ``node`` to the frontier and EXPAND removes
    it and appends it to the explored/visited order. ``frontier_position``
    preserves stack ordering for DFS without copying the entire stack.
    """

    """
    Thuật toán chạy
    ↓ tạo nhiều SearchStep
    SearchResult.steps
    ↓
    MapWidget và AlgorithmStatePanel
    ↓
    Hiển thị node đang xét, frontier, explored, cạnh được phát hiện
    
    
    SearchStep dùng để ghi lại một sự kiện xảy ra trong lúc thuật toán tìm đường, sau đó GUI phát lại các sự kiện theo thứ tự để tạo hoạt ảnh.
    
    Giả sử BFS tìm đường từ A tới D:
    Thuật toán có thể tạo danh sách sự kiện
    steps = [
    SearchStep(StepType.EXPAND, node_id="A"),

    SearchStep(
        StepType.DISCOVER,
        node_id="B",
        edge_from="A",
        edge_to="B",
    ),

    SearchStep(
        StepType.DISCOVER,
        node_id="C",
        edge_from="A",
        edge_to="C",
    ),

    SearchStep(StepType.EXPAND, node_id="B"),

    SearchStep(
        StepType.DISCOVER,
        node_id="D",
        edge_from="B",
        edge_to="D",
    ),

    SearchStep(StepType.EXPAND, node_id="D"),

    SearchStep(StepType.FINISH, node_id="D"),
    ]
    
    GUI phát lại từng bước
    Bước 1: đang xét A
    Bước 2: phát hiện B qua cạnh A → B
    Bước 3: phát hiện C qua cạnh A → C
    Bước 4: đang xét B
    Bước 5: phát hiện D qua cạnh B → D
    Bước 6: đang xét D
    Bước 7: kết thúc
    """

    def __init__(
        self,
        step_type: StepType,
        node_id: str = None,
        edge_from: str = None,
        edge_to: str = None,
        metrics: dict = None,  # g, h, f of heuristic function
        frontier=None,
        explored=None,
        visited_order=None,
        frontier_position: str = None,
    ):
        self.step_type = step_type
        self.node_id = node_id
        self.edge_from = edge_from
        self.edge_to = edge_to
        self.metrics = metrics or {}
        # Optional state snapshots keep playback deterministic and allow the UI
        # to move both forwards and backwards without re-running an algorithm.
        self.frontier = None if frontier is None else list(frontier)
        self.explored = None if explored is None else list(explored)
        self.visited_order = None if visited_order is None else list(visited_order)
        self.frontier_position = frontier_position

    def to_dict(self):
        """
        Serialize to the plain-dict schema the GUI / JavaScript side consumes.
        Fields that are None are omitted to keep the JSON payload small.
        """
        data = {"type": self.step_type.value}

        if self.node_id is not None:
            data["node"] = self.node_id

        if self.edge_from is not None:
            data["from"] = self.edge_from

        if self.edge_to is not None:
            data["to"] = self.edge_to

        if self.metrics:
            data["metrics"] = dict(self.metrics)

        if self.frontier is not None:
            data["frontier"] = list(self.frontier)

        if self.explored is not None:
            data["explored"] = list(self.explored)

        if self.visited_order is not None:
            data["visited_order"] = list(self.visited_order)

        if self.frontier_position is not None:
            data["frontier_position"] = self.frontier_position

        return data

    def __repr__(self):
        parts = [f"type={self.step_type.value}"]
        if self.node_id is not None:
            parts.append(f"node={self.node_id}")
        if self.edge_from is not None or self.edge_to is not None:
            parts.append(f"edge={self.edge_from}->{self.edge_to}")
        if self.metrics:
            parts.append(f"metrics={self.metrics}")
        return f"SearchStep({', '.join(parts)})"


class SearchResult:
    """
    Standard return object for search algorithms.

    GUI code can consume steps directly, while algorithm code can also expose
    path, total cost, visited order, success state, and a human-readable message.
    """

    """
    Là kết quả chuẩn mà thuật toán trả về
    Nhờ dùng chung một kiểu, GUI không cần biết thuật toán nào vừa chạy. Nó chỉ cần đọc:
    result.path
    result.success
    result.steps
    result.total_cost
    """

    """
    SearchResult
├── Kết quả chính: path, success, message, total_cost
├── Trực quan hóa: steps, visited_order
├── Số liệu tuyến: distance, time, segments, congestion
└── Hiệu năng và so sánh: runtime, frontier, comparison
    """

    def __init__(
        self,
        path=None,
        steps=None,
        total_cost: float = 0.0,
        success: bool = False,
        message: str = "",
        visited_order=None,
        runtime_ms: float = 0.0,
        total_distance=None,
        estimated_time=None,
        goal_visit_order=None,
        algorithm="",
        segments=None,
        total_time=None,
        congestion_penalty=None,
        explored_nodes=None,
        processing_time_ms=None,
        max_frontier_size=None,
        comparison=None,
    ):
        self.path = path or []
        self.steps = steps or []
        self.total_cost = float(total_cost)
        self.success = success
        self.message = message
        self.visited_order = visited_order or []
        self.runtime_ms = float(runtime_ms)
        self.total_distance = None if total_distance is None else float(total_distance)
        self.estimated_time = None if estimated_time is None else float(estimated_time)
        # Ordered delivery destinations for multi-location searches. This is
        # intentionally separate from ``visited_order``, which records graph
        # nodes expanded by the search algorithm.
        self.goal_visit_order = list(goal_visit_order or [])
        self.algorithm = str(algorithm or "")
        self.segments = list(segments or [])
        self.total_time = (
            self.estimated_time if total_time is None else _finite_float(total_time)
        )
        self.congestion_penalty = (
            None
            if congestion_penalty is None
            else _finite_float(congestion_penalty)
        )
        self.explored_nodes = (
            len(self.visited_order)
            if explored_nodes is None
            else max(0, int(explored_nodes))
        )
        self.processing_time_ms = (
            self.runtime_ms
            if processing_time_ms is None
            else _finite_float(processing_time_ms)
        )
        self.max_frontier_size = (
            None if max_frontier_size is None else max(0, int(max_frontier_size))
        )
        self.comparison = comparison

    def to_dict(self):
        """
        Serialize the whole result into one JSON-ready dict.
        """
        return {
            "success": self.success,
            "path": list(
                self.path
            ),  # Đường đi cuối cùng thuật toán tìm uddowjc, chứa ID của tất cả các node trên tuyến
            "total_cost": self.total_cost,
            "message": getattr(self, "message", ""),
            "visited_order": list(
                self.visited_order
            ),  # Thứ tự các node mà thuật toán đã lấy ra để xét/mở rộng.
            "runtime_ms": self.runtime_ms,
            "processing_time_ms": self.processing_time_ms,
            "total_distance": self.total_distance,
            "estimated_time": self.estimated_time,
            "total_time": self.total_time,
            "congestion_penalty": self.congestion_penalty,
            "explored_nodes": self.explored_nodes,
            "max_frontier_size": self.max_frontier_size,
            "segments": [
                segment.to_dict() if hasattr(segment, "to_dict") else dict(segment)
                for segment in self.segments
            ],
            "comparison": (
                self.comparison.to_dict()
                if hasattr(self.comparison, "to_dict")
                else self.comparison
            ),
            "goal_visit_order": list(self.goal_visit_order),
            # Accept both SearchStep objects and plain dicts (mock steps),
            # so mixed lists still serialize cleanly.
            "steps": [
                step.to_dict() if hasattr(step, "to_dict") else step
                for step in self.steps
            ],
        }

    def __repr__(self):
        return (
            f"SearchResult(success={self.success}, "
            f"path={self.path}, "
            f"total_cost={self.total_cost})"
        )


class Graph:
    def __init__(self):
        # Map Node ID to Node Object
        self.nodes = {}
        self.adjacency_list = {} # Directed Adjacency List mapping Node ID to its outgoing Edge objects
        # #NhatHuyChanged: maintain incoming edges for efficient reverse search.
        self.incoming_adjacency_list = {}
        # Max distance
        self.max_distance = 1.0
        # Max time
        self.max_time = 1.0

    def add_node(self, node: Node):
        """Register a node into the graph network and initialize its adjacency list."""
        self.nodes[node.id] = node
        if node.id not in self.adjacency_list:
            self.adjacency_list[node.id] = []
        if node.id not in self.incoming_adjacency_list:
            self.incoming_adjacency_list[node.id] = []

    def add_edge(self, edge: Edge):
        """
        Add an edge to the graph.
        Automatically handles one-way constraints and creates a reverse edge if the road type direction is specified as 'two-way'.
        """
        # Add the forward edge
        if edge.from_node not in self.adjacency_list:
            self.adjacency_list[edge.from_node] = []

        self.adjacency_list[edge.from_node].append(edge)
        self.incoming_adjacency_list.setdefault(edge.to_node, []).append(edge)

        # If it is a two-way street, create the reverse path
        if not edge.is_one_way:
            reverse_edge = edge.reversed()

            if reverse_edge.from_node not in self.adjacency_list:
                self.adjacency_list[reverse_edge.from_node] = []

            self.adjacency_list[reverse_edge.from_node].append(reverse_edge)
            self.incoming_adjacency_list.setdefault(
                reverse_edge.to_node, []
            ).append(reverse_edge)

    def get_node(self, node_id):
        return self.nodes.get(node_id)

    def get_neighbors(self, node_id: str):
        """Return all outgoing edges from a node."""
        return self.adjacency_list.get(node_id, [])

    def get_incoming_neighbors(self, node_id: str):
        """Return directed edges whose destination is ``node_id``."""
        return self.incoming_adjacency_list.get(node_id, [])

    def get_edge(self, from_node: str, to_node: str):
        """Return the first edge from from_node to to_node, or None."""
        for edge in self.adjacency_list.get(from_node, []):
            if edge.to_node == to_node:
                return edge
        return None

    def clear(self):
        self.nodes.clear()
        self.adjacency_list.clear()
        self.incoming_adjacency_list.clear()
