# Annotated diff: `feature/redesign_ui_3` → `feature/nlp-comparision-model`

## 0. Phạm vi và cách lập diff

- Baseline: `feature/redesign_ui_3` tại commit `13fe9e9c30abba21b4ad32e5bbab6813a4f8aee7`.
- Phía feature: working tree hiện tại của `feature/nlp-comparision-model` ngày 04/08/2026.
- `HEAD` của hai nhánh hiện cùng trỏ tới `13fe9e9`. Vì Route Comparison chưa được commit, `git diff feature/redesign_ui_3...HEAD` sẽ rỗng. Tài liệu này so baseline với **working tree hiện tại**, bao gồm hai file code/test mới chưa track.
- `diff.md` là tài liệu được tạo từ phép so sánh này nên không được tính vào thống kê code bên dưới.
- `.claude/`, `AGENTS.md` và `CLAUDE.md` là file hướng dẫn/cấu hình cục bộ, không thuộc chức năng Route Comparison và không được đưa vào diff tính năng.

Đây là logical annotated diff: mọi thay đổi hành vi đều được liệt kê, còn code snippet chỉ giữ phần quan trọng để tài liệu có thể review được. Raw diff của ba file đã track có thể xem bằng:

```powershell
git diff feature/redesign_ui_3 -- `
  src/models/models.py `
  src/gui/delivery_panel.py `
  src/gui/main_window.py
```

Hai file mới cần đọc trực tiếp vì chưa được Git theo dõi:

```text
src/algorithms/route_comparison.py
tests/test_route_comparison.py
```

## 1. Tổng quan thay đổi

| Trạng thái | File | Dòng thay đổi | Trách nhiệm |
| --- | --- | ---: | --- |
| Modified | `src/models/models.py` | `+204/-6` | Model metric, comparison mode, explanation và schema `SearchResult` mở rộng. |
| New | `src/algorithms/route_comparison.py` | 552 dòng | Metric chuẩn hóa, tạo route thứ hai, so sánh, optimality và sinh giải thích tiếng Việt. |
| Modified | `src/gui/delivery_panel.py` | `+326/-1` | `RouteComparisonPanel` với hai mode, bảng metric và explanation. |
| Modified | `src/gui/main_window.py` | `+207/-45` | Worker, cache, mode switching và thay Comparison placeholder bằng panel thật. |
| New | `tests/test_route_comparison.py` | 442 dòng | 16 test cho engine, worker, serialization và GUI. |

Tổng phần code/test: `+1731/-52` dòng. Không sửa trực tiếp BFS, DFS, UCS, A* hoặc Genetic Algorithm; các thuật toán tiếp tục dùng registry và contract `run_algorithm(name, graph, start, goal)` hiện có.

## 2. Kiến trúc trước và sau

### 2.1. `feature/redesign_ui_3`

```text
Algorithm
  → SearchResult
  → Map/Graph playback
  → Result Summary

Comparison tab
  → placeholder "Coming soon"
```

Baseline chỉ tính `total_distance`, `estimated_time` và `route_details` trong `MainWindow._enrich_result_metrics`. Không có type cho route segment/metrics/comparison, không có alternative route, không có thuật toán thứ hai và không có explanation generator.

### 2.2. `feature/nlp-comparision-model`

```text
Primary Algorithm
  → SearchResult
  → Canonical RouteMetrics
  ├── DIFFERENT_ALGORITHMS
  │     → run_algorithm(algorithm B, same graph/start/goal)
  └── SAME_ALGORITHM_ALTERNATIVE
        → run_algorithm(algorithm A, constrained graph view)
  → RouteComparison
  → RouteExplanationGenerator
  → Comparison tab

SearchResult/SearchStep
  → Map View và Graph View như baseline
```

Comparison nằm sau algorithm result, không nhét logic giải thích vào BFS/DFS/UCS/A*/GA và không chuyển toàn bộ phép tính lên GUI.

## 3. `src/models/models.py`

### 3.1. Serialization số hữu hạn

```diff
+def _finite_float(value, default=0.0):
+    try:
+        number = float(value)
+    except (TypeError, ValueError):
+        return float(default)
+    return number if math.isfinite(number) else float(default)
```

Mọi metric mới đi qua `_finite_float` để payload không chứa `NaN` hoặc `Infinity`, đặc biệt khi serialize sang JSON/UI.

### 3.2. Model route chuẩn hóa

```diff
+@dataclass
+class RouteSegment:
+    from_node: str
+    to_node: str
+    distance: float
+    travel_time: float
+    congestion: int
+    congestion_penalty: float
+    total_cost: float
+    road_name: str = ""
+    road_type: str = ""
+    risk: int = 0

+@dataclass
+class RouteMetrics:
+    path: List[str]
+    segments: List[RouteSegment]
+    total_distance: float
+    total_time: float
+    congestion_penalty: float
+    total_cost: float
+    high_congestion_segments: List[RouteSegment]
+    valid: bool
```

- `RouteSegment` biểu diễn một directed edge của route và giữ road metadata phục vụ explanation.
- `RouteMetrics` là dữ liệu algorithm-independent. Mọi route, bất kể được BFS/DFS/UCS/A*/GA tạo, đều được đo lại bởi cùng một hàm.
- `valid=False` phân biệt route không hợp lệ với route hợp lệ có tổng metric bằng 0, ví dụ `start == goal`.

### 3.3. Explanation và comparison mode

```diff
+@dataclass
+class RouteExplanation:
+    text: str = ""
+    optimality_statement: str = ""

+class ComparisonMode(Enum):
+    DIFFERENT_ALGORITHMS = "different_algorithms"
+    SAME_ALGORITHM_ALTERNATIVE = "same_algorithm_alternative"
```

`ComparisonMode.coerce` nhận cả enum và chuỗi từ Qt/serialization, đồng thời từ chối mode không hỗ trợ.

### 3.4. `RouteComparison`

```diff
+@dataclass
+class RouteComparison:
+    algorithm: str
+    selected: RouteMetrics
+    alternative: Optional[RouteMetrics]
+    mode: ComparisonMode
+    comparison_algorithm: str
+    cost_mode: str
+    winners: Dict[str, str]
+    differences: Dict[str, float]
+    explanation: RouteExplanation
```

Payload giữ cả tên tương thích cũ và tên trung lập cho mode khác thuật toán:

```json
{
  "mode": "different_algorithms",
  "primary_algorithm": "Breadth-First Search (BFS)",
  "comparison_algorithm": "Uniform Cost Search (UCS)",
  "cost_mode": "optimal",
  "selected": {},
  "alternative": {},
  "route_a": {},
  "route_b": {},
  "winners": {},
  "differences": {},
  "explanation": {}
}
```

`selected`/`alternative` được giữ để không phá code Comparison đã viết trước đó; `route_a`/`route_b` làm rõ nghĩa khi so hai thuật toán ngang hàng.

### 3.5. Mở rộng `SearchResult` theo kiểu additive

Các field mới đều có default nên constructor của các thuật toán cũ không phải đổi:

```diff
 class SearchResult:
     def __init__(
         ...,
+        algorithm="",
+        segments=None,
+        total_time=None,
+        congestion_penalty=None,
+        explored_nodes=None,
+        processing_time_ms=None,
+        max_frontier_size=None,
+        comparison=None,
     ):
```

Thay đổi đi kèm:

- `found` là alias property của `success`.
- `route_details` được dựng từ canonical segments.
- `total_cost` do thuật toán báo cáo vẫn được giữ; canonical comparison cost nằm trong `RouteMetrics.total_cost`.
- `to_dict` serialize algorithm, segments, total time, congestion penalty, processing metrics và comparison.
- Các giá trị số cũ (`total_cost`, `runtime_ms`, distance/time) cũng được bảo vệ bằng `_finite_float`.

## 4. `src/algorithms/route_comparison.py` — file mới

### 4.1. Cost và congestion chuẩn

```python
CANONICAL_COST_MODE = "optimal"
HIGH_CONGESTION_THRESHOLD = 4
METRIC_EPSILON = 1e-6
```

`calculate_route_metrics(graph, path, ..., cost_mode="optimal")`:

1. Kiểm tra graph, node và từng directed edge của path.
2. Dựng `RouteSegment` từ `distance`, `travel_time`, `congestion`, `risk`, `note`, `road_type`.
3. Tính `totalDistance`, `totalTime`, `congestionPenalty` và `totalCost` bằng cùng một vòng lặp.
4. Gọi `edge.calculate_cost(mode=cost_mode)` cho mọi route.
5. Gắn các segment có congestion từ mức 4 vào `high_congestion_segments`.

Không thuật toán nào được phép tự cung cấp metric so sánh theo công thức riêng.

### 4.2. Enrich `SearchResult`

`enrich_search_result` gắn canonical metrics vào result nhưng không ghi đè `result.total_cost` do thuật toán trả về. Hàm còn:

- đếm explored nodes từ `visited_order`;
- chuyển runtime thành `processing_time_ms`;
- phục hồi `max_frontier_size` từ snapshot hoặc delta `SearchStep`;
- dựng `route_details` cho Result Summary.

Logic metric cũ trong `MainWindow._enrich_result_metrics` được xóa để model/service là nguồn duy nhất.

### 4.3. Read-only constrained graph view

```diff
+class _EdgeFilteredGraph:
+    def __init__(self, graph, excluded_edges):
+        self.nodes = graph.nodes
+        self.adjacency_list = {
+            node_id: [edge for edge in graph.get_neighbors(node_id)
+                      if edge_key not in excluded_edges]
+            for node_id in graph.nodes
+        }
```

View dùng chung node và edge object của graph nguồn, chỉ tạo adjacency mapping đã lọc. Nó không xóa cạnh, không sửa trọng số và không đổi traffic trên graph gốc. `get_node`, `get_neighbors`, `get_edge` và fallback `__getattr__` giữ interface mà BFS/DFS/UCS/A*/GA đang dùng.

### 4.4. Mode `SAME_ALGORITHM_ALTERNATIVE`

`AlternativeRouteSelector.select` thực hiện:

1. Xác thực Selected route.
2. Lấy các cạnh của Selected theo thứ tự từ gần goal trở về start để ưu tiên route có prefix chung dài.
3. Với từng cạnh, tạo `_EdgeFilteredGraph` ẩn đúng cạnh đó.
4. Gọi lại `run_algorithm` bằng **chính tên thuật toán đã tạo Selected**, cùng start và goal.
5. Loại candidate thất bại, trùng Selected, có loop hoặc không còn hợp lệ trên graph gốc.
6. Trả candidate hợp lệ đầu tiên và tính metric trên graph gốc.

Đây không phải Dijkstra nội bộ và không phải chạy tất cả thuật toán. Alternative là kết quả của cùng public algorithm dưới ràng buộc “phải khác Selected”.

### 4.5. Mode `DIFFERENT_ALGORITHMS`

`build_route_comparison` yêu cầu `comparison_algorithm` khác primary algorithm, sau đó gọi:

```python
run_algorithm(
    comparison_algorithm,
    graph,
    requested_start_id,
    requested_goal_id,
)
```

- Dùng đúng graph object của primary run.
- Dùng start/goal người dùng yêu cầu, kể cả khi primary algorithm không tìm được path.
- Dùng cùng edge/traffic snapshot trong graph.
- Hai route được đo lại bằng `calculate_route_metrics` thay vì so trực tiếp cost riêng của từng thuật toán.

### 4.6. Winner và difference

`compare_routes` tính cho bốn metric:

| Key | Ý nghĩa | Tốt hơn khi |
| --- | --- | --- |
| `distance` | Tổng khoảng cách | thấp hơn |
| `time` | Tổng thời gian ước tính | thấp hơn |
| `congestion_penalty` | Tổng điểm congestion | thấp hơn |
| `total_cost` | Cost chuẩn `optimal` | thấp hơn |

Chênh lệch nhỏ hơn `METRIC_EPSILON` được xem là `tie`. Difference có dấu bằng `route A - route B` hoặc `Selected - Alternative`.

### 4.7. Optimality statement

`optimality_statement` không mặc định tuyên bố mọi route là tối ưu:

- UCS: chỉ xác nhận tối ưu theo canonical total cost khi kiểm tra được mọi edge cost đều không âm.
- BFS: chỉ bảo đảm ít cạnh nhất trong graph không trọng số, không bảo đảm distance/time/total cost.
- DFS: không bảo đảm optimality.
- GA: heuristic ngẫu nhiên, không bảo đảm global optimum.
- A*: chỉ bảo đảm khi heuristic admissible/consistent với cost; Haversine hiện chưa được chứng minh cho cost tổng hợp distance + time + congestion + risk.

### 4.8. Rule-based Vietnamese explanation

`RouteExplanationGenerator` dùng template, không gọi AI/LLM. Nội dung gồm:

- Mode và thuật toán tạo mỗi route.
- Kết luận tốt hơn theo distance, time, total cost và congestion penalty.
- Gợi ý route/algorithm theo canonical total cost.
- Tên các segment congestion cao, road name/type và congestion level.
- Optimality statement riêng cho từng thuật toán khi mode khác thuật toán.

Path dài không bị lặp lại trong đoạn explanation; path được hiển thị riêng trong UI. Nhờ vậy explanation ngắn hơn bản mô tả Selected/Alternative cũ.

## 5. `src/gui/delivery_panel.py`

### 5.1. `RouteComparisonPanel`

Panel mới được thêm cạnh `ResultSummaryPanel` và phát signal:

```python
comparison_requested = pyqtSignal(str, str)
```

Các control mới:

- `mode_combo`:
  - Different algorithms;
  - Same algorithm · alternative route.
- `algorithm_combo`: chọn thuật toán thứ hai, chỉ bật trong mode khác thuật toán.
- Bảng metric 5 cột: Metric, route thứ nhất, route thứ hai, Difference, Better.
- Hai route label có thể select/copy.
- Explanation label tiếng Việt.

### 5.2. Label thay đổi theo mode

| Mode | Cột/route thứ nhất | Cột/route thứ hai |
| --- | --- | --- |
| `DIFFERENT_ALGORITHMS` | Route A | Route B |
| `SAME_ALGORITHM_ALTERNATIVE` | Selected | Alternative |

Context label hiển thị `algorithm A vs algorithm B` hoặc `algorithm · same algorithm`.

### 5.3. State của panel

- `reset`: chưa có comparison nhưng vẫn cho chọn mode trước khi chạy.
- `set_running`: khóa control trong lúc primary/comparison worker chạy.
- `set_recomputing`: báo đang đổi mode và khóa control tạm thời.
- `set_error`: giữ active result để người dùng có thể chọn mode khác sau lỗi.
- `set_comparison`: đồng bộ mode, algorithms, route labels, metric table, winner và explanation.
- Nếu không có route thứ hai, panel hiện `Second route not found` thay vì crash hoặc tạo số metric giả.

Compatibility alias `DeliveryPanel = ResultSummaryPanel` của baseline vẫn được giữ.

## 6. `src/gui/main_window.py`

### 6.1. `SearchWorker`

Constructor nhận thêm optional parameters:

```diff
 SearchWorker(
     algorithm,
     graph,
     start_id,
     goal_id,
+    comparison_mode,
+    comparison_algorithm,
 )
```

Sau primary `run_algorithm`, worker ghi runtime và gọi `build_route_comparison` trên cùng worker thread. Default vẫn là same-algorithm mode để giữ tương thích cho caller cũ không truyền tham số mới.

### 6.2. `ComparisonWorker`

Worker mới chỉ phục vụ recompute khi người dùng đổi mode/algorithm sau primary run. Nó nhận graph, active result, start/goal và cache key, rồi phát:

```python
completed = pyqtSignal(object, str, object)
failed = pyqtSignal(str, object)
```

Signal mang `source_result` để MainWindow bỏ qua kết quả stale nếu active search đã thay đổi.

### 6.3. Comparison tab thật thay placeholder

```diff
-comparison = QWidget()
-comparison_text = QLabel("Coming soon ...")
-self.info_tabs.addTab(comparison, "Comparison · Soon")
+self.comparison_panel = RouteComparisonPanel(self.available_algorithms)
+self.comparison_scroll = QScrollArea()
+self.comparison_scroll.setWidget(self.comparison_panel)
+self.info_tabs.addTab(self.comparison_scroll, "Comparison")
```

Compact và desktop layout đều dùng label `Comparison`; không còn chuỗi `Comparison · Soon`.

### 6.4. Search flow

`on_run_search_clicked` bổ sung:

1. Đồng bộ primary algorithm vào panel.
2. Đọc current comparison mode và secondary algorithm.
3. Từ chối different-algorithms mode nếu thiếu algorithm B.
4. Xóa comparison cache của search cũ.
5. Đặt panel vào running state.
6. Truyền cấu hình comparison cho `SearchWorker`.

`_on_search_completed` lưu comparison đầu tiên vào cache rồi tiếp tục Map/Graph playback như baseline.

`on_animation_finished` vẫn cập nhật Result Summary và bổ sung `comparison_panel.set_comparison(result.comparison)`. Map View, Graph View và Algorithm State không đọc/ghi logic comparison.

### 6.5. Mode switching và cache

Cache key:

```text
<comparison_mode>:<comparison_algorithm>
```

`on_comparison_requested`:

- trả ngay cached comparison nếu đã tính trong active search;
- nếu chưa có, tạo `ComparisonWorker` trên QThread;
- không chạy hai comparison worker đồng thời;
- gắn result mới vào cùng active `SearchResult` khi hoàn tất;
- hiển thị alert/log nhưng vẫn cho retry mode khác khi thất bại.

Cache bị xóa khi load graph mới, chạy primary search mới hoặc Reset, bảo đảm không tái sử dụng route từ traffic/graph/start/goal cũ.

### 6.6. Metric logic được đưa khỏi GUI

`MainWindow._enrich_result_metrics` bị xóa. Phần cộng distance/time/route details chuyển sang `enrich_search_result`, nên Result Summary và Comparison dùng chung canonical segments thay vì hai implementation khác nhau.

## 7. `tests/test_route_comparison.py` — file mới

16 test mới bao phủ:

1. Canonical distance/time/congestion/total cost và road name.
2. Different-algorithms mode gọi algorithm B đúng một lần với cùng graph/start/goal.
3. Same-algorithm mode chỉ gọi lại đúng primary algorithm.
4. Constrained graph view dùng chung node/edge data và không mutate graph gốc.
5. Không có alternative khi graph chỉ có một route.
6. Từ chối different-algorithms mode nếu hai algorithm trùng nhau.
7. Algorithm B vẫn nhận requested start/goal khi primary thất bại.
8. Serialization có mode, hai algorithm, cost mode và route A/B.
9. Explanation ngắn, có gợi ý theo total cost và không lặp full path.
10. High-congestion segment xuất hiện đúng tên đường và congestion level.
11. Optimality statement thay đổi theo algorithm và điều kiện edge cost.
12. `start == goal` là route hợp lệ với metric 0 nhưng không có alternative.
13. Canonical comparison không ghi đè algorithm-reported `SearchResult.total_cost`.
14. `SearchWorker` tạo đúng requested comparison mode.
15. Comparison panel chuyển đúng Route A/B ↔ Selected/Alternative.
16. Panel xử lý missing route và cho đổi mode lại sau recompute error.

Các test này chạy cùng năm test trong `tests/test_search_contract.py` để khóa contract Map/Graph hiện hữu.

## 8. Call flow sau thay đổi

### 8.1. Initial search

```text
MainWindow.on_run_search_clicked
  → SearchWorker.run
    → run_algorithm(primary)
    → build_route_comparison
      → enrich_search_result(primary)
      → [mode branch]
      → compare_routes
      → RouteExplanationGenerator.generate
    → SearchResult.comparison
  → MainWindow._on_search_completed
  → MapWidget playback
  → GraphWidget receives the same SearchStep stream
  → MainWindow.on_animation_finished
    ├── ResultSummaryPanel.set_result
    └── RouteComparisonPanel.set_comparison
```

### 8.2. Switch comparison mode

```text
RouteComparisonPanel.comparison_requested
  → MainWindow.on_comparison_requested
  ├── cache hit → set_comparison
  └── cache miss
      → ComparisonWorker.run
      → build_route_comparison
      → MainWindow._on_comparison_completed
      → cache + set_comparison
```

## 9. Tính tương thích và giới hạn

### 9.1. Tương thích được giữ

- Không đổi signature công khai của `run_algorithm`.
- Không sửa implementation BFS/DFS/UCS/A*/GA.
- Các field mới của `SearchResult` đều optional.
- `result.total_cost` cũ không bị canonical metric ghi đè.
- Map View và Graph View tiếp tục dùng cùng `SearchResult`/`SearchStep` playback.
- Không gọi API AI/LLM.
- Graph nguồn và traffic edge không bị mutate khi tìm Alternative.

### 9.2. Giới hạn có chủ đích

- Alternative cùng thuật toán là kết quả dưới ràng buộc loại một cạnh của Selected; nó không có nghĩa algorithm sẽ tự chọn route đó nếu chạy lại không ràng buộc.
- Alternative có thể tốt hơn Selected đối với DFS, BFS, GA hoặc A* hiện tại vì các algorithm này không bảo đảm tối ưu theo canonical total cost.
- GA không expose population/candidate qua `SearchResult`; same-algorithm alternative vì thế vẫn dùng public `run_algorithm` thay vì đọc state nội bộ.
- Repository chưa có cost-mode selector hoặc traffic snapshot object. Comparison dùng graph object hiện tại và `cost_mode="optimal"` cho cả hai route.

## 10. GitNexus findings và impact

GitNexus xác nhận baseline symbols còn tồn tại:

- `ALGORITHMS`, `get_algorithms`, `run_algorithm` trong `src/algorithms/algorithms.py`.
- `SearchResult` trong `src/models/models.py`.
- `SearchWorker.run`, `MainWindow.on_run_search_clicked`, `_on_search_completed`, `create_workspace`, `on_animation_finished` trong `src/gui/main_window.py`.
- `ResultSummaryPanel.set_result` trong `src/gui/delivery_panel.py`.

Baseline execution flow quan trọng:

```text
build_ui → create_sidebar → create_algorithm_group → get_algorithms
on_run_search_clicked → SearchWorker.run → run_algorithm
on_animation_finished → ResultSummaryPanel / playback state updates
```

Impact trước chỉnh sửa:

- `SearchResult`: MEDIUM, 9 importer trực tiếp và 13 symbol upstream tổng cộng.
- `SearchWorker`, workspace và GUI handlers: LOW.
- `diff.md`: LOW, không có caller hoặc execution flow phụ thuộc.
- Các symbol trong file mới trả UNKNOWN vì GitNexus index đang ở commit baseline và không index file untracked.

`detect_changes(scope="compare", base_ref="feature/redesign_ui_3")` báo CRITICAL với 42 changed symbols và 24 affected flows. Zero-context raw diff cho thấy báo cáo over-map nhiều method chỉ bị dịch line number trong ba file lớn; thay đổi nội dung thực nằm trong model Comparison, Comparison panel, worker và các handler integration đã liệt kê trong tài liệu này. GitNexus structural check không phát hiện import cycle.

## 11. Kết quả kiểm tra hiện tại

| Kiểm tra | Kết quả | Ý nghĩa |
| --- | --- | --- |
| `pytest -q tests/test_route_comparison.py tests/test_search_contract.py` | `21 passed` | Hai mode, metric, explanation, worker, GUI và search contract đạt. |
| `python -m compileall -q src tests` | Đạt | Python source/test compile được. |
| `git diff --check` | Đạt | Không có whitespace error; chỉ có cảnh báo LF sẽ đổi sang CRLF trên Windows. |
| GitNexus structural check | `0` cycles | Không tạo circular import. |
| `pytest -q` | `21 passed, 3 failed` | Ba lỗi baseline bên dưới không phát sinh từ Comparison. |

Ba lỗi baseline còn lại:

1. `src/models/test_models.py::test_ai_graph_components` dùng constructor cũ `Node(x=..., y=...)` trong khi model hiện nhận `lat/lon`.
2. `src/models/test_models.py::test_build_graph_from_mock_data` cần file không tồn tại `data/mock_data.json`.
3. `src/models/test_models.py::test_build_graph_from_legacy_map_data` cần file không tồn tại `data/map_data.json`.

Không sửa ba lỗi này vì nằm ngoài phạm vi Route Comparison.

## 12. Kết luận review

1. Comparison tab từ placeholder trở thành tính năng có hai mode chuyển đổi được.
2. Different-algorithms mode so hai public algorithm trên cùng request và cùng graph/traffic.
3. Same-algorithm mode không còn dùng Dijkstra nội bộ; Alternative được tạo bằng đúng primary algorithm dưới ràng buộc route khác.
4. Mọi metric đều đi qua một canonical calculator, không phụ thuộc cách từng algorithm tự báo cost.
5. Explanation hoàn toàn rule-based, ngắn, có congestion, recommendation và optimality statement thận trọng.
6. Comparison recompute chạy ngoài GUI thread và được cache theo active search.
7. SearchResult được mở rộng additive; Map View, Graph View và search algorithm contract không bị thay đổi.
