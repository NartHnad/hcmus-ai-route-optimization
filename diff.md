# Annotated diff: `develop` → `feature/redesign_ui_3`

## 0. Phạm vi so sánh

- Baseline: nhánh `develop`, commit `04940e3`.
- Phía feature: working tree hiện tại của `feature/redesign_ui_3` ngày 03/08/2026.
- Tại thời điểm lập tài liệu, `develop`, `origin/develop` và `HEAD` của feature cùng trỏ tới `04940e3`. Vì các thay đổi redesign chưa được commit, lệnh `git diff develop...HEAD` sẽ rỗng. Tài liệu này vì thế so `develop` với **working tree hiện tại**, bao gồm cả file mới chưa track.
- `plan.md` đang bị ignore bởi `.gitignore`; file đó được dùng làm nguồn giải thích thiết kế, không được tính là file nguồn trong patch.

Đây là **logical annotated diff**: các đoạn không đổi được lược bằng `...` để tài liệu đọc được. Mỗi đoạn diff bên dưới đều có phần “Giải thích” ngay sau nó. Nếu cần raw patch không chú thích cho 13 file đã track, dùng `git diff develop -- src tests`; năm file mới được mô tả đầy đủ theo từng trách nhiệm trong tài liệu này.

## 1. Tổng quan thay đổi

| Trạng thái | File | Vai trò chính |
| --- | --- | --- |
| Modified | `src/algorithms/a_star.py` | Bổ sung metric `h`, metadata priority cho playback. |
| Modified | `src/algorithms/algorithms.py` | Loại Mock 3 khỏi danh sách thuật toán công khai. |
| Modified | `src/algorithms/bfs.py` | Chuyển event visualization sang delta đúng ngữ nghĩa queue. |
| Modified | `src/algorithms/dfs.py` | Giữ visited order xác định và metadata stack. |
| Modified | `src/algorithms/genetic_algorithm.py` | Chặn vòng lặp vô hạn và cung cấp snapshot phù hợp với GA. |
| New | `src/algorithms/ucs.py` | Thêm Uniform Cost Search theo contract visualization chung. |
| Modified | `src/data/data_loader.py` | Đọc metadata nhẹ cho danh sách dataset. |
| Modified | `src/models/models.py` | Mở rộng `SearchStep`/`SearchResult` cho state và metric UI. |
| New | `src/gui/algorithm_state_panel.py` | Panel Current/Frontier/Explored/Visited/metrics. |
| Modified | `src/gui/delivery_panel.py` | Thay panel delivery tĩnh bằng Result Summary. |
| Modified | `src/gui/main_window.py` | Responsive UI, worker thread, state machine, Map/Graph, playback profiles và manual mode. |
| Modified | `src/gui/map_widget.py` | Playback controller có backpressure, batching, Previous và Step by step. |
| Modified | `src/gui/assets/map.html` | Leaflet renderer theo delta, Canvas, batch rendering, legend và large-graph LOD. |
| New | `src/gui/graph_widget.py` | Python bridge cho Graph View. |
| New | `src/gui/assets/graph.html` | Canvas node-edge renderer có pan/zoom/state/metrics. |
| Modified | `src/gui/themes/light.qss` | Design system và responsive style cho light theme. |
| Modified | `src/gui/themes/dark.qss` | Design system tương ứng cho dark theme. |
| New | `tests/test_search_contract.py` | Contract và regression tests cho thuật toán/UI payload. |

Phần đã track thay đổi khoảng `+2737/-1115` dòng. Năm file mới bổ sung khoảng 1.255 dòng. Thay đổi lớn nằm ở UI/render/playback; logic chọn đường của BFS/DFS/A*/GA được giữ nguyên và có regression test khóa path/cost.

---

## 2. Search algorithms và contract dữ liệu

### 2.1. `src/algorithms/a_star.py`

```diff
 steps.append(
     SearchStep(
         StepType.EXPAND,
         node_id=current,
-        metrics={"g": current_g, "f": current_f},
+        metrics={
+            "g": current_g,
+            "h": max(0.0, current_f - current_g),
+            "f": current_f,
+        },
     )
 )
```

**Giải thích:** A* vốn đã tính `f = g + h` để chọn node nhưng event `EXPAND` chỉ đưa `g/f` sang UI. Bổ sung `h` giúp Algorithm State và Graph View hiển thị đủ ba giá trị mà không tính lại heuristic ở renderer. `max(0.0, ...)` tránh sai số floating-point tạo `h` âm rất nhỏ. Việc này chỉ bổ sung dữ liệu quan sát, không đổi heap hay thứ tự chọn node.

```diff
-steps.append(SearchStep(StepType.FINISH, node_id=goal_id))
+steps.append(
+    SearchStep(
+        StepType.FINISH,
+        node_id=goal_id,
+        metrics={"g": current_g, "h": 0.0, "f": current_f},
+    )
+)
```

**Giải thích:** Step cuối giữ metric của goal để panel không mất `g/h/f` ngay khi chuyển từ node cuối sang trạng thái finished. Goal có heuristic bằng 0. Path và cost vẫn lấy từ kết quả A* cũ.

```diff
 SearchStep(
     StepType.DISCOVER,
     node_id=neighbor,
     edge_from=current,
     edge_to=neighbor,
     metrics={"g": tentative_g, "h": h, "f": f},
+    frontier_position="priority",
 )
```

**Giải thích:** `frontier_position="priority"` nói cho state panel biết frontier này là priority queue. Metadata chỉ phục vụ biểu diễn; quyết định pop vẫn do heap A* hiện có thực hiện.

### 2.2. `src/algorithms/algorithms.py`

```diff
-try:
-    from src.algorithms.mock3_algorithm import mock3_search
-    ALGORITHMS["Mock 3 Search"] = mock3_search
-except ImportError:
-    pass
```

**Giải thích:** Mock 3 không tuân thủ đầy đủ contract và không phải thuật toán cần demo. Bỏ đăng ký làm danh sách UI chỉ còn DFS, BFS, UCS, A* và GA. File mock không bị xóa nên code thử nghiệm cũ vẫn còn, chỉ không xuất hiện như tính năng chính thức.

### 2.3. `src/algorithms/bfs.py`

```diff
 for edge in graph.get_neighbors(current):
     neighbor = edge.to_node
-    steps.append(SearchStep(StepType.DISCOVER, ...))
     if neighbor in visited:
         continue
     visited.add(neighbor)
     came_from[neighbor] = (current, edge)
     queue.append(neighbor)
+    steps.append(
+        SearchStep(
+            StepType.DISCOVER,
+            node_id=neighbor,
+            edge_from=current,
+            edge_to=neighbor,
+            frontier_position="back",
+        )
+    )
```

**Giải thích:** `develop` phát DISCOVER trước khi kiểm tra `visited`, khiến cùng một node có thể xuất hiện nhiều lần trong visualization dù không được enqueue. Bản mới chỉ phát event sau khi node thật sự được thêm vào queue. `back` mô tả đúng FIFO. Thứ tự queue và path BFS không đổi; chỉ event UI khớp với thao tác thật.

```diff
-steps.append(SearchStep(StepType.FINISH, node_id=goal_id))
+steps.append(
+    SearchStep(
+        StepType.FINISH,
+        node_id=goal_id,
+    )
+)
```

**Giải thích:** Đây chủ yếu là chuẩn hóa format để các event constructor nhất quán và dễ bổ sung metadata. Không có thay đổi hành vi.

### 2.4. `src/algorithms/dfs.py`

```diff
-try:
-    from models.models import SearchResult, SearchStep, StepType
-except ImportError:
-    from src.models.models import SearchResult, SearchStep, StepType
+from src.models.models import SearchResult, SearchStep, StepType
```

**Giải thích:** Chuẩn hóa import tuyệt đối theo package `src`, tránh cùng class được load dưới hai module path khác nhau tùy cách chạy chương trình.

```diff
 steps = []
+visited_order = []
 ...
 visited.add(current)
+visited_order.append(current)
 ...
-visited_order=list(visited),
+visited_order=visited_order,
```

**Giải thích:** `set` không bảo đảm thứ tự duyệt dùng cho Result Summary. List mới ghi đúng thứ tự node được expand, trong khi `visited` vẫn dùng để tra membership O(1). Việc chọn node của stack không đổi.

```diff
 if edge.to_node not in visited:
+    stack.append((edge.to_node, path + [edge.to_node]))
     steps.append(
         SearchStep(
             StepType.DISCOVER,
             node_id=edge.to_node,
             edge_from=edge.from_node,
             edge_to=edge.to_node,
+            frontier_position="front",
         )
     )
-    stack.append((edge.to_node, path + [edge.to_node]))
```

**Giải thích:** Event được phát đúng sau thao tác push, và `front` cho state panel biết đây là stack/LIFO. Dòng push không thay đổi điều kiện hay thứ tự vòng lặp nên traversal cũ được giữ nguyên.

### 2.5. `src/algorithms/genetic_algorithm.py`

```diff
 population = []
+attempts = 0
+max_attempts = max(200, population_size * 100)
-while len(population) < population_size:
+while len(population) < population_size and attempts < max_attempts:
+    attempts += 1
     candidate = random_path(...)
```

**Giải thích:** Graph khó hoặc không có đủ đường hợp lệ có thể làm vòng tạo population chạy vô hạn trên GUI worker. Giới hạn số lần thử biến tình huống đó thành kết quả hữu hạn. Đây là guard an toàn, không thay fitness hoặc cách xếp hạng chromosome hợp lệ.

```diff
+population_target = len(population)
 ...
-elite_count = max(1, population_size // 5)
+elite_count = max(1, population_target // 5)
 ...
-while len(new_population) < population_size:
+while len(new_population) < population_target and child_attempts < max_attempts:
     ...
+if len(new_population) < population_target:
+    new_population.extend(population[: population_target - len(new_population)])
```

**Giải thích:** Nếu guard ban đầu chỉ tạo được population nhỏ hơn yêu cầu, các thế hệ sau phải dùng kích thước thực tế thay vì tiếp tục chờ kích thước không thể đạt. Khi crossover không tạo đủ child hợp lệ, elite cũ lấp phần thiếu để thuật toán tiến lên thay vì treo.

```diff
 SearchStep(
     StepType.DISCOVER,
     ...,
     metrics={"path_length": len(candidate)},
+    frontier=candidate[i + 1 :],
+    explored=candidate[: i + 1],
+    visited_order=candidate[: i + 1],
 )
```

**Giải thích:** GA không có queue/stack delta giống graph search. Với producer nhỏ này, snapshot đường ứng viên là cách chính xác để Algorithm State phục hồi frontier/explored. Core BFS/DFS/UCS/A* vẫn dùng delta gọn để tránh O(V²) memory.

### 2.6. `src/algorithms/ucs.py` — file mới

```diff
+def ucs(graph, start_id, goal_id):
+    queue = [(0.0, start_id)]
+    best_cost = {start_id: 0.0}
+    came_from = {start_id: (None, None)}
+    explored = set()
+
+    while queue:
+        current_cost, current = heapq.heappop(queue)
+        if current in explored or current_cost > best_cost.get(current, float("inf")):
+            continue
+        explored.add(current)
+        visited_order.append(current)
+        steps.append(SearchStep(StepType.EXPAND, node_id=current,
+                                metrics={"g": current_cost}))
```

**Giải thích:** File hiện thực Uniform Cost Search bằng min-heap. `best_cost` loại entry cũ, `came_from` dựng path, `explored` khóa node đã chốt. Thuật toán tối ưu theo `edge.calculate_cost()` và phát cùng contract `EXPAND/DISCOVER/FINISH` như các thuật toán khác.

```diff
+candidate = current_cost + edge.calculate_cost()
+if candidate >= best_cost.get(neighbor, float("inf")):
+    continue
+best_cost[neighbor] = candidate
+came_from[neighbor] = (current, edge)
+heapq.heappush(queue, (candidate, neighbor))
+steps.append(
+    SearchStep(
+        StepType.DISCOVER,
+        node_id=neighbor,
+        edge_from=current,
+        edge_to=neighbor,
+        metrics={"g": candidate},
+        frontier_position="priority",
+    )
+)
```

**Giải thích:** Chỉ relaxation cải thiện cost mới tạo event và đưa node vào priority queue. Metadata `priority` giúp UI biểu diễn đúng mà không can thiệp heap. File này cũng làm import UCS vốn đã có trong registry thực sự hoạt động.

### 2.7. `src/data/data_loader.py`

```diff
+import json
 ...
+def get_dataset_options():
+    """Return lightweight display metadata without constructing every graph."""
+    options = []
+    for filename in get_json_datasets():
+        path = DATA_DIR / filename
+        node_count = None
+        try:
+            with open(path, "r", encoding="utf-8") as file:
+                raw_nodes = json.load(file).get("nodes", [])
+            node_count = len(raw_nodes)
+        except (OSError, ValueError, TypeError):
+            pass
+        options.append({"filename": filename, "node_count": node_count})
+    return options
```

**Giải thích:** Sidebar cần hiện tên dataset và số node trước khi load. Hàm chỉ đọc JSON metadata, không dựng toàn bộ `Graph`/`Edge`, nên tránh chi phí không cần thiết lúc khởi động. Nếu một file lỗi, filename vẫn xuất hiện với count rỗng để thao tác load có thể báo lỗi đúng chỗ.

### 2.8. `src/models/models.py`

```diff
 class SearchStep:
     def __init__(
         self,
         step_type,
         node_id=None,
         edge_from=None,
         edge_to=None,
         metrics=None,
+        frontier=None,
+        explored=None,
+        visited_order=None,
+        frontier_position=None,
     ):
         ...
+        self.frontier = None if frontier is None else list(frontier)
+        self.explored = None if explored is None else list(explored)
+        self.visited_order = None if visited_order is None else list(visited_order)
+        self.frontier_position = frontier_position
```

**Giải thích:** Contract hỗ trợ hai kiểu producer: compact delta cho graph search lớn và snapshot tùy chọn cho GA/legacy. Copy list tại biên model tránh caller thay đổi snapshot sau khi event đã tạo. `frontier_position` giữ semantics queue/stack/priority mà không copy toàn frontier mỗi step.

```diff
 def to_dict(self):
     ...
+    if self.frontier is not None:
+        data["frontier"] = list(self.frontier)
+    if self.explored is not None:
+        data["explored"] = list(self.explored)
+    if self.visited_order is not None:
+        data["visited_order"] = list(self.visited_order)
+    if self.frontier_position is not None:
+        data["frontier_position"] = self.frontier_position
```

**Giải thích:** Chỉ serialize field thực sự có dữ liệu để payload JavaScript nhỏ. UI có thể phân biệt “không có snapshot, hãy áp delta” với “snapshot rỗng”.

```diff
 class SearchResult:
     def __init__(
         ...,
+        runtime_ms=0.0,
+        total_distance=None,
+        estimated_time=None,
     ):
         ...
+        self.runtime_ms = float(runtime_ms)
+        self.total_distance = None if total_distance is None else float(total_distance)
+        self.estimated_time = None if estimated_time is None else float(estimated_time)
```

**Giải thích:** Result Summary cần runtime thực, tổng khoảng cách và thời gian ước tính bên cạnh path cost. `None` biểu diễn metric không tính được, khác với giá trị 0 hợp lệ. Các tham số mới có default nên producer cũ vẫn tương thích.

---

## 3. State và Result UI

### 3.1. `src/gui/algorithm_state_panel.py` — file mới

```diff
+class StateList(QFrame):
+    def __init__(self, title, parent=None):
+        ...
+        self.summary = QLabel("—")
+        self.details = QTextEdit()
+        self.details.setReadOnly(True)
+        self._details_timer = QTimer(self)
+        self._details_timer.setSingleShot(True)
+        self._details_timer.setInterval(120)
+        self._details_timer.timeout.connect(self._refresh_details)
```

**Giải thích:** `StateList` tái sử dụng cho Frontier, Explored và Visited. Phần tóm tắt luôn nhẹ; danh sách đầy đủ chỉ materialize khi người dùng mở `View all`. Debounce 120 ms tránh dựng lại `QTextDocument` hàng nghìn dòng ở mỗi playback tick.

```diff
+class AlgorithmStatePanel(QFrame):
+    def update_step(self, step):
+        history = step.get("_history")
+        batch = step.get("_batch")
+        if history is not None:
+            self._reset_state()
+            for item in history:
+                self._apply_delta(item)
+        elif batch:
+            for item in batch:
+                self._apply_delta(item)
+        else:
+            self._apply_delta(step)
+        ...
```

**Giải thích:** Panel nhận cùng event stream với Map/Graph. `_history` dùng khi Previous cần phục hồi, `_batch` dùng khi autoplay gom event, còn event đơn dùng cho Next/Step by step. Vì cùng một reducer xử lý cả ba, state không lệch renderer.

```diff
+def _apply_delta(self, step):
+    uses_snapshot = any(
+        key in step for key in ("frontier", "explored", "visited_order")
+    )
+    if uses_snapshot:
+        ... # thay state bằng snapshot legacy/GA
+    elif event_type in {"discover", "update"}:
+        self._add_frontier(node, step)
+    elif event_type == "expand":
+        self._remove_frontier(node)
+        self._explored.append(node)
+        self._visited.append(node)
```

**Giải thích:** Reducer ưu tiên snapshot nếu producer cung cấp; nếu không, nó phục hồi state từ delta compact. Đây là phần cho phép BFS/DFS/UCS/A* không lưu ba list đầy đủ ở mỗi step, giảm memory từ xu hướng O(V²) xuống gần O(number of events).

### 3.2. `src/gui/delivery_panel.py`

```diff
-class DeliveryPanel(QGroupBox):
-    # Chỉ gồm các QLabel Algorithm/Distance/Time/Visited/Status
+class MetricCard(QFrame):
+    ...
+class ResultSummaryPanel(QGroupBox):
+    """Single source of truth for the current run result."""
+    ...
+    self.distance = MetricCard("Distance")
+    self.runtime = MetricCard("Runtime")
+    self.visited = MetricCard("Visited nodes")
+    self.cost = MetricCard("Path cost")
+    self.estimated_time = MetricCard("Estimated time")
```

**Giải thích:** Panel cũ là placeholder và không được đồng bộ đầy đủ. Result Summary mới là nguồn duy nhất cho kết quả single-route, tách metric thành card để đọc nhanh và hỗ trợ responsive grid.

```diff
+def set_result(self, result, algorithm, start, goal):
+    success = bool(getattr(result, "success", False))
+    self.status_label.setText("Route found" if success else "No route found")
+    self.distance.set_value(...)
+    self.runtime.set_value(...)
+    self.visited.set_value(...)
+    self.cost.set_value(...)
+    self.estimated_time.set_value(...)
+    self.route_label.setText("Route: " + " → ".join(path))
+    ... # điền bảng từng segment
```

**Giải thích:** Kết quả chỉ được chốt sau playback finished, bao gồm success/failure, route, metric và chi tiết từng cạnh. `getattr` giữ tương thích với SearchResult cũ chưa có metric mở rộng.

```diff
+# Compatibility alias for older imports while keeping one canonical component.
+DeliveryPanel = ResultSummaryPanel
```

**Giải thích:** Alias tránh làm hỏng module khác nếu vẫn import tên `DeliveryPanel`, đồng thời toàn bộ implementation mới chỉ có một component chuẩn.

---

## 4. Main window và luồng ứng dụng

### 4.1. `src/gui/main_window.py` — worker thread và execution state

```diff
-from PyQt5.QtCore import Qt
+from PyQt5.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
 ...
+class SearchWorker(QObject):
+    completed = pyqtSignal(object, float)
+    failed = pyqtSignal(str)
+
+    @pyqtSlot()
+    def run(self):
+        try:
+            started = time.perf_counter()
+            result = run_algorithm(
+                self.algorithm, self.graph, self.start_id, self.goal_id
+            )
+            runtime_ms = (time.perf_counter() - started) * 1000
+            self.completed.emit(result, runtime_ms)
+        except Exception as exc:
+            self.failed.emit(str(exc))
```

**Giải thích:** `develop` chạy search trực tiếp trong GUI thread nên cửa sổ không repaint hoặc nhận click khi graph lớn. Worker chuyển phần tính toán nguyên trạng sang `QThread`; GUI chỉ nhận `SearchResult` và runtime qua signal. Thuật toán không bị đổi, chỉ nơi thực thi thay đổi để UI không treo.

```diff
+EXECUTION_STATES = {
+    "idle", "loading", "ready", "computing",
+    "running", "paused", "finished",
+}
 ...
+def _set_execution_state(self, state):
+    self.execution_state = state
+    self.run_button.setEnabled(state in {"ready", "finished"})
+    self.pause_button.setEnabled(
+        not manual_mode and state in {"running", "paused"}
+    )
+    ...
+    controls_locked = state in {"loading", "computing", "running", "paused"}
+    self.dataset_combo.setEnabled(not controls_locked)
+    self.algorithm_combo.setEnabled(not controls_locked and bool(self.available_algorithms))
+    self.speed_combo.setEnabled(state not in {"loading", "computing"})
```

**Giải thích:** Bản cũ enable/disable button rải trong từng handler, dễ lệch trạng thái timer thật. State machine tập trung mọi control, thêm `loading/computing` để phân biệt đang render graph, đang tính search và đang playback. Manual mode dùng cùng state `paused` nhưng khóa Pause/Resume để không bật timer ngoài ý muốn.

### 4.2. Responsive shell và hierarchy mới

```diff
-self.content_layout = QHBoxLayout()
-self.sidebar = self.create_sidebar()
-self.content_layout.addWidget(self.sidebar)
-self.map_widget = MapWidget()
-self.content_layout.addWidget(self.map_widget, stretch=1)
+self.main_splitter = QSplitter(Qt.Horizontal)
+self.sidebar_scroll = self.create_sidebar()
+self.workspace = self.create_workspace()
+self.main_splitter.addWidget(self.sidebar_scroll)
+self.main_splitter.addWidget(self.workspace)
+self.main_splitter.setSizes([320, 940])
```

**Giải thích:** Sidebar fixed 280 px và năm group dọc làm layout bị cắt ở màn hình thấp. `QSplitter` cho người dùng kéo biên 260–520 px, `QScrollArea` giữ tất cả control truy cập được, còn workspace nhận phần diện tích còn lại.

```diff
-self.light_button = QPushButton("Light Mode")
-self.dark_button = QPushButton("Dark Mode")
-self.mobile_button = QPushButton("📱 Mobile")
+self.sidebar_toggle = QPushButton("☰")
+self.title_label = QLabel("Route Lab")
+self.map_view_button = QPushButton("Map View")
+self.graph_view_button = QPushButton("Graph View")
+self.state_toggle = QPushButton("Hide state")
+self.status_badge = QLabel("Not ready")
+self.theme_button = QPushButton("Dark mode")
```

**Giải thích:** Header mới ưu tiên navigation và trạng thái thực thi thay vì ba nút mode rời. Mobile panel tĩnh bị bỏ; responsive layout thực sự dùng sidebar drawer và tabs, nên không còn hai nơi hiển thị dữ liệu dễ lệch nhau.

```diff
+def _apply_responsive_layout(self):
+    compact = self.width() < self.COMPACT_BREAKPOINT
+    if compact != self._compact_mode:
+        self._enter_compact_layout() if compact else self._exit_compact_layout()
+    ...
+
+def _enter_compact_layout(self):
+    # Sidebar thành drawer; State/Result/Log/Compare dùng tab.
+    ...
```

**Giải thích:** Responsive breakpoint 880 px thay thế nút “Mobile” mô phỏng thủ công. Cùng widget thật được tái bố trí, không clone state. Cửa sổ hỗ trợ tối thiểu 430×620 theo plan.

### 4.3. Dataset và node selectors

```diff
-available_datasets = get_json_datasets()
-self.dataset_combo.addItems(available_datasets)
+for option in get_dataset_options():
+    label = self.friendly_dataset_name(option["filename"])
+    if option["node_count"] is not None:
+        label += f" · {option['node_count']} nodes"
+    self.dataset_combo.addItem(label, option["filename"])
```

**Giải thích:** Text hiển thị được tách khỏi filename thật bằng `itemData`. Người dùng thấy tên khu vực thân thiện và quy mô dataset nhưng loader vẫn nhận đúng tên file.

```diff
-self.start_combo = QComboBox()
-self.goal_combo = QComboBox()
+self.start_combo = self.searchable_combo()
+self.goal_combo = self.searchable_combo()
 ...
+item = QStandardItem(f"{node.id} — {node.name}")
+item.setData(node.id, Qt.UserRole)
+model.invisibleRootItem().appendRows(items)
+self.start_combo.setModel(model)
+self.goal_combo.setModel(model)
```

**Giải thích:** Với hàng nghìn node, ID thô khó chọn. Hai combo dùng chung model, hiện `ID — Name`, sắp xếp tự nhiên và completer `MatchContains`. `UserRole` vẫn giữ ID chuẩn để gọi thuật toán.

### 4.4. Workspace Map/Graph/State/Result

```diff
-self.map_widget = MapWidget()
+self.map_widget = MapWidget()
+self.graph_widget = GraphWidget()
+self.visual_stack = QStackedWidget()
+self.visual_stack.addWidget(self.map_widget)
+self.visual_stack.addWidget(self.graph_widget)
+self.algorithm_state = AlgorithmStatePanel()
+self.result_panel = ResultSummaryPanel()
+self.info_tabs.addTab(self.result_scroll, "Result")
+self.info_tabs.addTab(self.event_log, "Event log")
+self.info_tabs.addTab(comparison, "Comparison · Soon")
```

**Giải thích:** Graph View là renderer thứ hai của cùng `SearchResult`, không phải thuật toán riêng. Algorithm State, Result và Event Log được tách thành khu vực có thể resize/tab thay vì nhét log vào sidebar. Comparison chỉ là placeholder đúng phạm vi kế hoạch.

```diff
+def _set_visualization_mode(self, mode):
+    graph_active = mode == "graph"
+    self.visual_stack.setCurrentWidget(
+        self.graph_widget if graph_active else self.map_widget
+    )
+    self.graph_widget.set_render_enabled(graph_active)
+    self.map_widget.set_visual_updates_enabled(not graph_active)
+    if not graph_active:
+        self.map_widget.refresh_current_visualization()
```

**Giải thích:** Chỉ renderer đang thấy mới repaint, tránh trả gấp đôi chi phí Canvas mỗi event. Khi quay lại Map, controller dựng snapshot hiện tại để hình ảnh bắt kịp state đã nhận trong lúc ẩn.

### 4.5. Load readiness và xử lý lỗi

```diff
-self.graph = load_dataset(filename)
-self.map_widget.draw_graph(self.graph)
-self.run_button.setEnabled(True)
+self._set_execution_state("loading")
+self.graph = load_dataset(filename)
+self._pending_renderers = {"map", "graph"}
+self._ready_renderers.clear()
+self.map_widget.draw_graph(self.graph)
+self.graph_widget.draw_graph(self.graph)
+...
+def on_visualization_render_ready(self, renderer):
+    self._ready_renderers.add(renderer)
+    if self.execution_state == "loading" and self._active_view in self._ready_renderers:
+        self._finish_visualization_load()
```

**Giải thích:** `develop` mở Run ngay sau khi gửi JavaScript, dù WebEngine chưa dựng xong graph. Bản mới dùng render token và signal readiness; active view sẵn sàng thì control mở, renderer ẩn tiếp tục chuẩn bị nền và không chặn người dùng.

```diff
+def on_visualization_render_failed(self, renderer, message):
+    if renderer != self._active_view:
+        self.show_alert(
+            f"{title} View could not be prepared; the active view is still usable.",
+            "warning",
+        )
+        return
+    self._set_execution_state("idle")
+    self.show_alert(f"{title} rendering failed: {message}", "error")
```

**Giải thích:** Lỗi renderer ẩn không làm hỏng renderer đang dùng. Nếu active view lỗi, state quay về an toàn và có alert/log rõ thay vì chỉ `print` hoặc để button ở trạng thái sai.

### 4.6. Search lifecycle và result metrics

```diff
-result = run_algorithm(algorithm, self.graph, start_id, goal_id)
-self.map_widget.draw_map_step_by_step(result, interval)
+self._set_execution_state("computing")
+self._search_thread = QThread(self)
+self._search_worker = SearchWorker(algorithm, self.graph, start_id, goal_id)
+self._search_worker.moveToThread(self._search_thread)
+self._search_worker.completed.connect(self._on_search_completed)
+self._search_worker.failed.connect(self._on_search_failed)
+self._search_thread.start()
```

**Giải thích:** Đây là wiring dùng worker đã mô tả ở trên. Thread/worker được `deleteLater` khi xong để không rò QObject; input bị khóa trong state `computing` nên graph không bị thay giữa lúc thuật toán đọc.

```diff
+def _enrich_result_metrics(self, result):
+    distance = 0.0
+    estimated_time = 0.0
+    route_details = []
+    for from_node, to_node in zip(result.path, result.path[1:]):
+        edge = self.graph.get_edge(from_node, to_node)
+        distance += edge.distance
+        estimated_time += edge.travel_time
+        route_details.append({...})
+    result.total_distance = distance if complete else None
+    result.estimated_time = estimated_time if complete else None
+    result.route_details = route_details if complete else []
```

**Giải thích:** Search algorithm tiếp tục trả path/cost; UI layer suy ra metric trình bày từ các edge đã chọn. Tách enrichment khỏi thuật toán tránh làm BFS/DFS/A*/UCS phụ thuộc widget hoặc format bảng.

### 4.7. Autoplay profiles và Step by step

```diff
-self.speed_combo.addItems(["0 ms", "100 ms", "250 ms", "500 ms", "1000 ms"])
+self.speed_combo.addItem("Instant", {"interval_ms": 0, "target_duration_ms": 0, ...})
+self.speed_combo.addItem("Fast · ~5 s", {"interval_ms": 50, "target_duration_ms": 5000, ...})
+self.speed_combo.addItem("Balanced · ~15 s", {"interval_ms": 100, "target_duration_ms": 15000, ...})
+self.speed_combo.addItem("Detailed · ~30 s", {"interval_ms": 200, "target_duration_ms": 30000, ...})
+self.speed_combo.addItem(
+    "Step by step · Manual",
+    {
+        "name": "Step by step",
+        "interval_ms": 100,
+        "target_duration_ms": 0,
+        "manual": True,
+        "hint": "Manual playback only; use Previous and Next ...",
+    },
+)
+self.speed_combo.setCurrentIndex(2)  # Balanced
```

**Giải thích:** Nhãn ms/event không thực tế cho search hàng nghìn event vì còn thời gian render. Bốn profile autoplay dùng thời lượng mục tiêu 0/5/15/30 giây; Balanced là mặc định. Profile thứ năm đặt cờ `manual`, không giả lập bằng interval rất lớn, nên controller có thể bảo đảm timer không chạy.

```diff
+manual_mode = profile.get("manual", False)
+self._set_execution_state("paused" if manual_mode else "running")
+self.map_widget.draw_map_step_by_step(
+    result,
+    profile["interval_ms"],
+    profile["target_duration_ms"],
+    manual_mode=manual_mode,
+)
```

**Giải thích:** Search vẫn tính toàn bộ kết quả như cũ. Chỉ playback bắt đầu ở `paused/manual` và step 0 khi chọn Step by step; không event visualization nào được tự áp trước lần bấm Next đầu tiên.

```diff
 def on_replay_clicked(self):
     ...
     self.map_widget.replay_animation()
+    if self.current_playback_profile().get("manual", False):
+        self._set_execution_state("paused")
+        self.log_event("INFO", "Manual playback returned to the initial state.")
+    else:
+        self._set_execution_state("running")
```

**Giải thích:** Replay ở profile cũ vẫn tự chạy. Trong Step by step, Replay chỉ reset Map/Graph/State về step 0 để người dùng tiếp tục Next thủ công; đây là hành vi khác biệt có chủ đích của profile mới.

```diff
+if manual_mode:
+    self.pause_button.setEnabled(False)
+    self.pause_button.setText("Manual mode")
+    labels["paused"] = ("Manual", "paused")
```

**Giải thích:** Pause/Resume không có ý nghĩa khi autoplay bị cấm. Khóa nút và đổi badge giúp trạng thái thủ công rõ ràng, còn Previous/Next/Replay/Reset vẫn hoạt động qua state machine hiện có.

### 4.8. Playback controls và event log

```diff
-self.pause_button = QPushButton("Pause")
-self.resume_button = QPushButton("Resume")
-self.next_button = QPushButton("Next Step")
+self.pause_button = QPushButton("Pause")  # toggle Pause/Resume
+self.previous_button = QPushButton("Previous")
+self.next_button = QPushButton("Next")
+self.replay_button = QPushButton("Replay")
+self.reset_button = QPushButton("Reset")
```

**Giải thích:** Gộp Pause/Resume loại hai nút loại trừ nhau và bổ sung Previous. Lưới playback 2×2/3 hàng giảm chiều cao sidebar; Run vẫn là primary action.

```diff
+def on_step_changed(self, step):
+    self.graph_widget.apply_playback_event(step)
+    self.algorithm_state.update_step(step)
+    event_type = step.get("type", "unknown").upper()
+    index = step.get("_index", 0)
+    total = step.get("_total", 0)
+    ...
+    self.log_event("STEP", f"{index}/{total} · {detail}.")
```

**Giải thích:** Một event từ MapWidget được fan-out sang Graph View, Algorithm State và Event Log. Log phân biệt EXPAND/DISCOVER/UPDATE/FINISH và có index; không còn gọi chung mọi hành vi là “Visiting”.

```diff
+def log_event(self, level, message):
+    timestamp = datetime.now().strftime("%H:%M:%S")
+    self.event_log.append(
+        f'<span class="event-time">{timestamp}</span> '
+        f'<span class="event-{level.lower()}">{html.escape(level)}</span> '
+        f'{html.escape(message)}'
+    )
```

**Giải thích:** Event Log có timestamp và level, escape nội dung trước khi đưa vào rich text. Nó được chuyển khỏi sidebar sang tab để không chiếm chiều cao điều khiển.

---

## 5. Playback controller và Map bridge

### 5.1. `src/gui/map_widget.py` — signals và trạng thái nội bộ

```diff
 class MapWidget(QWebEngineView):
     animation_finished = pyqtSignal()
     step_changed = pyqtSignal(dict)
+    playback_state_changed = pyqtSignal(str)
+    graph_ready = pyqtSignal()
+    graph_render_failed = pyqtSignal(str)
 ...
+    self._interval_ms = 100
+    self._target_duration_ms = 15000
+    self._auto_batch_size = 1
+    self._playback_deadline = None
+    self._manual_mode = False
+    self._js_step_in_flight = False
+    self._playback_generation = 0
+    self._pending_navigation = None
```

**Giải thích:** Controller mới báo state/readiness cho MainWindow thay vì để UI đoán từ timer. Các field mới phục vụ adaptive batching, manual mode, backpressure và hủy callback cũ bằng generation token.

```diff
-self._timer = QTimer(self)
-self._timer.timeout.connect(self.apply_next_step)
+self._timer = QTimer(self)
+self._timer.setSingleShot(True)
+self._timer.timeout.connect(self._on_timer_timeout)
```

**Giải thích:** Repeating timer có thể tiếp tục đẩy JavaScript khi WebEngine chưa xử lý xong. Single-shot chỉ schedule nhịp mới sau callback render trước, tạo backpressure và giữ queue IPC có giới hạn.

### 5.2. Graph serialization và readiness

```diff
-edges = [mỗi directed edge trong adjacency_list]
+visual_edges = {}
+for outgoing_edges in graph.adjacency_list.values():
+    for edge in outgoing_edges:
+        pair = tuple(sorted((edge.from_node, edge.to_node)))
+        visual_edges.setdefault(pair, physical_edge_payload)
+        visual_edges[pair]["directions"].append([edge.from_node, edge.to_node])
```

**Giải thích:** Graph lưu đường hai chiều thành hai directed edge nhưng renderer chỉ cần một physical line. Dedup giảm số polyline/canvas edge gần một nửa mà vẫn giữ `directions` để tô đúng chiều inspect/relax và vẽ arrow.

```diff
+def draw_graph(self, graph):
+    graph_data = self._serialize_graph(graph)
+    self._graph_generation += 1
+    graph_data["render_token"] = self._graph_generation
+    ...
+
+def _poll_graph_render(self, token):
+    self.page().runJavaScript("getGraphRenderState()", handle_state)
```

**Giải thích:** Leaflet render theo batch/rAF nên callback gọi hàm khởi tạo chưa đồng nghĩa graph đã xong. Token ngăn load cũ phát signal ready sau một load mới; polling mở Run đúng lúc renderer hoàn tất.

### 5.3. Khởi tạo autoplay/manual

```diff
-def draw_map_step_by_step(self, result, interval_ms=500):
+def draw_map_step_by_step(
+    self, result, interval_ms=100, target_duration_ms=15000,
+    manual_mode=False,
+):
     self.stop_animation()
     ...
+    self._manual_mode = bool(manual_mode)
+    self._is_paused = self._manual_mode
+    self._paused_at = time.perf_counter() if self._manual_mode else None
+    self._reset_playback_deadline()
+    self._recalculate_auto_batch_size()
```

**Giải thích:** Signature cũ vẫn tương thích nhờ default. Manual mode là state riêng, không dựa vào magic interval. Deadline và batch size chỉ ảnh hưởng autoplay.

```diff
-self._timer.setInterval(interval_ms)
-self._timer.start()
+if self._manual_mode:
+    self.playback_state_changed.emit("paused")
+    self._reset_renderer_then(lambda: None)
+else:
+    self.playback_state_changed.emit("running")
+    self._reset_renderer_then(lambda: self._schedule_next(token, delay=0))
```

**Giải thích:** Step by step reset visualization rồi đứng ở step 0, tuyệt đối không schedule timer. Bốn profile cũ đi nhánh else và tự chạy như trước.

```diff
+def _schedule_next(self, token=None, delay=None):
+    if (
+        token != self._playback_generation
+        or self._manual_mode
+        or self._is_paused
+        or self._step_index >= len(self._steps)
+    ):
+        return
+    self._timer.start(...)
```

**Giải thích:** Guard `manual_mode` là lớp bảo vệ trung tâm: kể cả callback cũ hoặc Resume bị gọi nhầm, timer vẫn không khởi động. Token bỏ qua schedule thuộc playback đã reset/replay.

### 5.4. Adaptive batching và backpressure

```diff
+def _recalculate_auto_batch_size(self, observed_update_ms=None):
+    remaining = len(self._steps) - self._step_index
+    remaining_budget_ms = max(
+        1.0, (self._playback_deadline - time.perf_counter()) * 1000
+    )
+    effective_update_ms = max(self._interval_ms, observed_update_ms or self._interval_ms)
+    target_updates = max(1, int(remaining_budget_ms / effective_update_ms))
+    self._auto_batch_size = max(1, math.ceil(remaining / target_updates))
```

**Giải thích:** Search lớn không thể chạy từng raw event trong 5/15/30 giây. Batch size được tính từ số event còn lại, deadline profile và thời gian render quan sát được. Đây chỉ là batching visualization; delta vẫn áp theo thứ tự.

```diff
+def _dispatch_steps(self, batch_size, instant=False):
+    if self._js_step_in_flight:
+        return
+    step_dicts = [...]
+    self._js_step_in_flight = True
+    if instant:
+        function_name = "renderInstantResult"
+    else:
+        function_name = "applyStep" if len(step_dicts) == 1 else "applySteps"
+    self._run_js_function(function_name, payload,
+        callback=lambda _: self._on_steps_rendered(token, step_dicts))
```

**Giải thích:** Chỉ một JavaScript update được in-flight. Instant gửi một final visualization thay vì hàng nghìn IPC call; batch gửi mảng event một lần. State/Log vẫn nhận `_batch` để xử lý đủ từng delta.

```diff
+def _on_steps_rendered(self, token, step_dicts):
+    self._js_step_in_flight = False
+    emitted = dict(step_dicts[-1])
+    if len(step_dicts) > 1:
+        emitted["_batch"] = step_dicts
+        emitted["_batch_size"] = len(step_dicts)
+    self.step_changed.emit(emitted)
+    ...
+    if not self._is_paused:
+        elapsed_ms = ...
+        remaining_delay = max(0, round(self._interval_ms - elapsed_ms))
+        self._schedule_next(token, delay=remaining_delay)
```

**Giải thích:** Cadence bao gồm cả thời gian WebEngine và Qt State/Log, không cộng thêm delay sau render như `develop`. Điều này làm Fast/Balanced/Detailed gần thời lượng công bố hơn và vẫn phản hồi Pause/Next.

### 5.5. Pause, Next, Previous, Replay và manual guard

```diff
 def resume_animation(self):
-    if self._is_paused and ...:
+    if not self._manual_mode and self._is_paused and ...:
         self._schedule_next(delay=0)
```

**Giải thích:** Resume giữ hành vi cũ cho autoplay nhưng là no-op trong Step by step. Đây là lớp bảo vệ thứ hai sau `_schedule_next`.

```diff
 def next_step(self):
+    if not self._steps or self._step_index >= len(self._steps):
+        return
     self._timer.stop()
+    self._is_paused = True
+    self.playback_state_changed.emit("paused")
+    if self._js_step_in_flight:
+        self._pending_navigation = "next"
+        return
-    self.apply_next_step()
+    self._dispatch_steps(1)
```

**Giải thích:** Next luôn đi đúng một raw event và chuyển autoplay sang paused. Nếu renderer đang bận, thao tác được queue thành một navigation duy nhất thay vì gửi JavaScript chồng lên nhau.

```diff
+def previous_step(self):
+    self._timer.stop()
+    self._is_paused = True
+    self._step_index -= 1
+    rendered_steps = [self._step_as_dict(i) for i in range(self._step_index)]
+    visual_snapshot = self._build_visual_snapshot(rendered_steps)
+    self._run_js_function("renderSnapshot", visual_snapshot, history_rendered)
```

**Giải thích:** `develop` không có Previous. Bản mới phục hồi một bước bằng snapshot trực quan bounded thay vì reset Leaflet rồi replay hàng chục nghìn event. `_history` vẫn được gửi sang Algorithm State/Graph để state chi tiết chính xác.

```diff
 def replay_animation(self):
     self.stop_animation()
     self._step_index = 0
+    self._is_paused = self._manual_mode
+    if self._manual_mode:
+        self.playback_state_changed.emit("paused")
+        self._reset_renderer_then(lambda: None)
+    else:
+        self.playback_state_changed.emit("running")
+        self._reset_renderer_then(lambda: self._schedule_next(token, delay=0))
```

**Giải thích:** Replay tự chạy đối với profile cũ; manual mode chỉ quay về step 0. Cùng một step list/result được tái sử dụng, không chạy lại thuật toán.

### 5.6. Renderer ẩn, theme và message bridge

```diff
+def set_visual_updates_enabled(self, enabled):
+    self._visual_updates_enabled = bool(enabled)
+
+def refresh_current_visualization(self):
+    rendered_steps = [self._step_as_dict(i) for i in range(self._step_index)]
+    self._run_js_function("renderSnapshot", self._build_visual_snapshot(rendered_steps))
+
+def show_message(self, text, level="info"):
+    self._run_js_function("showMapMessage", {"text": text, "level": level})
```

**Giải thích:** Map ẩn không repaint trong Graph View nhưng controller vẫn phát state. Khi map hiện lại, snapshot đồng bộ đúng bước. Theme/message đi qua bridge thay vì hardcode hoặc thao tác DOM từ MainWindow.

---

## 6. Map renderer

### 6.1. `src/gui/assets/map.html` — UI overlay và renderer nền

```diff
-<div id="map"></div>
-<div id="empty-message" class="map-empty-message">Waiting for graph data...</div>
+<div id="map"></div>
+<div id="map-message" class="map-message" data-level="info">...</div>
+<div id="legend" class="legend" aria-label="Map legend">
+    <button id="legend-toggle" class="legend__toggle">Map legend</button>
+    <div class="legend__body">
+        <div class="legend__item">Start</div>
+        <div class="legend__item">Goal</div>
+        <div class="legend__item">Current</div>
+        <div class="legend__item">Frontier</div>
+        <div class="legend__item">Explored</div>
+        <div class="legend__item">Final path</div>
+    </div>
+</div>
```

**Giải thích:** Empty label đơn được thay bằng message có level info/success/error và legend giải thích state trực quan. Legend tự thu gọn ở viewport hẹp, giúp Map View tự đủ ngữ cảnh mà không cần đọc Event Log.

```diff
+const canvasRenderer = L.canvas({ padding: 0.35, tolerance: 5 });
+const networkLayer = L.layerGroup().addTo(map);
+const stateLayer = L.layerGroup().addTo(map);
+const endpointLayer = L.layerGroup().addTo(map);
```

**Giải thích:** Canvas Leaflet phù hợp hàng nghìn node/edge hơn SVG DOM element cho từng shape. Tách base network, algorithm state và endpoint làm reset playback không xóa graph hoặc marker Start/Goal.

### 6.2. Batch graph rendering và large-graph LOD

```diff
-data.nodes.forEach(node => L.circleMarker(...).addTo(map));
-data.edges.forEach(edge => L.polyline(...).addTo(map));
+const renderEdgeBatch = () => {
+    const limit = Math.min(edgeCursor + EDGE_BATCH_SIZE, incoming.edges.length);
+    for (; edgeCursor < limit; edgeCursor += 1) {
+        ... // tạo physical polyline bằng Canvas
+    }
+    if (edgeCursor < incoming.edges.length) {
+        window.requestAnimationFrame(renderEdgeBatch);
+    } else {
+        window.requestAnimationFrame(renderNodeBatch);
+    }
+};
+window.requestAnimationFrame(renderEdgeBatch);
```

**Giải thích:** `develop` dựng toàn graph trong một JavaScript task, làm renderer treo và Qt không biết khi nào xong. Bản mới chia edge/node theo frame, cập nhật render state/token và giữ browser responsive. Edges được dựng trước để người dùng thấy network sớm.

```diff
+const largeGraph = incoming.nodes.length > 2000;
+...
+function ensureNodeLayer(nodeId) {
+    if (!nodeLayers.has(nodeId)) {
+        nodeLayers.set(nodeId, L.circleMarker(...));
+    }
+    return nodeLayers.get(nodeId);
+}
+
+function syncVisibleNodes() {
+    // Chỉ materialize node cần thấy theo zoom/state ở graph lớn.
+}
```

**Giải thích:** Với khoảng 8.000 node, vẽ tất cả marker chồng lên nhau vừa chậm vừa không đọc được. Large-graph LOD chỉ dựng node quan trọng hoặc nhìn thấy ở zoom phù hợp. Algorithm State vẫn giữ đủ explored/visited; giới hạn chỉ áp cho hình ảnh trên map.

```diff
+const graphRenderState = {
+    token: 0,
+    ready: false,
+    error: null,
+};
+function getGraphRenderState() { return { ...graphRenderState }; }
```

**Giải thích:** Python polling dùng object này để xác nhận đúng render token đã xong. Nếu exception xảy ra trong batch, `error` được trả về MainWindow thay vì playback bắt đầu trên graph chưa sẵn sàng.

### 6.3. Delta state thay cho quét toàn graph

```diff
+const frontier = new Set();
+const explored = new Set();
+const edgeStates = new Map();
+let currentNode = null;
+
 function applyStep(rawStep) {
+    const step = normalizeInput(rawStep);
+    const usesSnapshot = Array.isArray(step.frontier)
+        || Array.isArray(step.explored)
+        || Array.isArray(step.visited_order);
+    if (usesSnapshot) {
+        ... // phục hồi snapshot GA/legacy
+    } else if (step.type === 'expand') {
+        frontier.delete(step.node);
+        explored.add(step.node);
+    } else if (step.type === 'discover' || step.type === 'update') {
+        frontier.add(step.node);
+    }
+    ... // chỉ restyle node/edge liên quan
 }
```

**Giải thích:** Renderer cũ thường áp lại style toàn graph ở mỗi step. Reducer mới giữ Set/Map và chỉ đổi node/edge liên quan, giảm công việc từ O(V×S) về gần O(S). Snapshot vẫn tương thích cho GA/Previous.

```diff
+function applySteps(rawSteps) {
+    const steps = normalizeInput(rawSteps);
+    (Array.isArray(steps) ? steps : []).forEach(applyStep);
+}
+
+function renderSteps(rawSteps) {
+    resetVisualization();
+    (Array.isArray(steps) ? steps : []).forEach(applyStep);
+}
```

**Giải thích:** `applySteps` phục vụ batch autoplay mà không reset; `renderSteps` phục hồi history từ đầu. Cả hai gọi cùng `applyStep`, nên semantics event không có hai implementation khác nhau.

### 6.4. Instant, Previous snapshot và endpoint

```diff
+function renderInstantResult(rawStep) {
+    const step = normalizeInput(rawStep);
+    resetVisualization();
+    highlightPath(step.path || []);
+}
+
+function renderSnapshot(rawSnapshot) {
+    const snapshot = normalizeInput(rawSnapshot);
+    resetVisualization();
+    ... // dựng frontier/explored/current/edge/path đã tổng hợp
+}
```

**Giải thích:** Instant chỉ cần final path trên map, còn Python/State panel vẫn xử lý đủ delta. Previous nhận một bounded snapshot đã tổng hợp, tránh replay 16.000 DOM/style operations trên Leaflet.

```diff
-function updateSelection(selection) {
-    // đổi style node thường thành start/goal
-}
+function endpointIcon(kind, label) { ... }
+function refreshEndpointMarkers() {
+    // tạo marker S/G trong endpointLayer
+}
+function updateSelection(rawSelection) {
+    currentStart = selection.start || null;
+    currentGoal = selection.goal || null;
+    refreshEndpointMarkers();
+}
```

**Giải thích:** Start/Goal là marker S/G độc lập nên không bị event current/frontier/explored ghi đè. Cùng node có thể vừa là endpoint vừa có algorithm state mà vẫn đọc được.

```diff
+function setTheme(payload) {
+    currentTheme = normalizeInput(payload).theme === 'dark' ? 'dark' : 'light';
+    document.documentElement.dataset.theme = currentTheme;
+}
+
+function showMapMessage(payload) {
+    setMapMessage(true, escapedText, payload.level || 'info');
+}
```

**Giải thích:** Overlay theo theme và message được điều khiển qua API nhỏ từ Python. Tile OSM vẫn sáng theo quyết định trong plan; chỉ control/overlay/style vector đổi theme.

---

## 7. Graph View

### 7.1. `src/gui/graph_widget.py` — file mới

```diff
+class GraphWidget(QWebEngineView):
+    """Canvas graph renderer that mirrors MapWidget playback events."""
+
+    graph_ready = pyqtSignal()
+    graph_render_failed = pyqtSignal(str)
+
+    def __init__(self, parent=None):
+        ...
+        html_path = Path(__file__).resolve().parent / "assets" / "graph.html"
+        self.setHtml(...)
```

**Giải thích:** GraphWidget là bridge Python–WebEngine tương tự MapWidget nhưng không sở hữu timer hay thuật toán. MapWidget vẫn là playback controller duy nhất; GraphWidget chỉ mirror event.

```diff
+@staticmethod
+def _serialize_graph(graph):
+    ...
+    pair = tuple(sorted((edge.from_node, edge.to_node)))
+    ...
+    visual_edges[pair]["directions"].append(list(direction))
+    return {"nodes": nodes, "edges": list(visual_edges.values())}
```

**Giải thích:** Payload dedup physical edge giống Map View, nhưng thêm `cost`, `distance`, `travel_time`, road metadata và mọi direction để Graph Canvas vẽ label/arrow chính xác.

```diff
+def apply_playback_event(self, step):
+    if step.get("type") == "reset":
+        self.reset_visualization()
+        return
+    if step.get("_history") is not None:
+        self._run_js_function("renderSteps", step["_history"])
+        return
+    if step.get("_batch"):
+        self._run_js_function("applySteps", step["_batch"])
+        return
+    self._run_js_function("applyStep", step)
```

**Giải thích:** Graph View hiểu đủ event đơn, batch autoplay, history Previous và reset Replay. Nó không tự tăng step index nên không thể lệch Map/Algorithm State.

```diff
+def set_render_enabled(self, enabled):
+    self._render_enabled = bool(enabled)
+    self._run_js_function("setRenderEnabled", {"enabled": self._render_enabled})
```

**Giải thích:** Renderer ẩn vẫn giữ state JavaScript nhưng bỏ draw, tránh tốn CPU song song với Map. Khi mở Graph View, một draw mới hiển thị state hiện tại.

### 7.2. `src/gui/assets/graph.html` — file mới

```diff
+<canvas id="graph"></canvas>
+<div class="toolbar">
+    <button id="fit-button">Fit graph</button>
+    <button id="labels-button">Labels: Auto</button>
+</div>
+<div class="legend">Default · Frontier · Explored · Current · Final path</div>
+<div id="tooltip"></div>
```

**Giải thích:** Graph View là Canvas node-edge chuyên cho quan sát thuật toán, có Fit, label mode, legend và tooltip thay vì tái dùng Leaflet không phù hợp topology thuần.

```diff
+function buildLayout() {
+    if (graphData.nodes.length <= 120) {
+        // force layout cho graph nhỏ
+    } else {
+        // geographic normalization từ lat/lon cho graph lớn
+    }
+}
```

**Giải thích:** Force layout tách node graph nhỏ để topology dễ đọc; graph lớn dùng vị trí địa lý để tránh O(V²) force simulation. Đây là thay đổi renderer, không tác động graph model hay thuật toán.

```diff
+function mutateStep(rawStep) {
+    ...
+    if (usesSnapshot) {
+        ...
+    } else if (type === 'expand') {
+        frontier.delete(node);
+        explored.add(node);
+    } else if (type === 'discover' || type === 'update') {
+        frontier.add(node);
+    }
+    nodeMetrics.set(node, { ...oldMetrics, ...(step.metrics || {}) });
+}
+function applyStep(rawStep) { mutateStep(rawStep); scheduleDraw(); }
+function applySteps(rawSteps) { rawSteps.forEach(mutateStep); scheduleDraw(); }
```

**Giải thích:** Reducer phản chiếu Map renderer và giữ `g/h/f` theo node. Batch mutate toàn bộ event rồi chỉ draw một frame, đúng mục tiêu adaptive playback.

```diff
+function draw() {
+    ...
+    drawEdgeLabel(edge, from, to, colors);  // c:cost · d:distance
+    ...
+    drawNodeLabel(node, point, radius, colors, important); // name + g/h/f
+}
```

**Giải thích:** Graph View bổ sung thông tin mà Map View khó hiển thị: tên node, metric heuristic, cost/distance edge và direction. Node quan trọng luôn có label; node thường tùy zoom/label mode để tránh nhiễu.

```diff
+canvas.addEventListener('wheel', ...);       // zoom quanh con trỏ
+canvas.addEventListener('mousedown', ...);   // bắt đầu pan
+canvas.addEventListener('mousemove', ...);   // pan hoặc tooltip hit-test
+fitButton.addEventListener('click', fitGraph);
```

**Giải thích:** Interaction hoàn toàn ở renderer, không round-trip Python. Hit-test node/edge cung cấp tooltip nhưng không thay selection Start/Goal hoặc playback state.

---

## 8. Theme system

### 8.1. `src/gui/themes/light.qss`

```diff
-QMainWindow { background-color: #f2f4f8; }
-QPushButton { background-color: #4a90e2; ... }
+QWidget#appRoot { background: #f7f9fc; color: #182230; }
+QFrame#appHeader { background: #ffffff; border: 1px solid #e4e7ec; ... }
+QPushButton#primaryButton { background: #1570ef; color: white; ... }
+QPushButton#secondaryButton { background: #ffffff; border: 1px solid #d0d5dd; ... }
+QPushButton#tertiaryButton, QPushButton#iconButton { ... }
```

**Giải thích:** Style toàn cục “mọi button màu xanh” được tách theo object name để tạo hierarchy primary/secondary/tertiary. Scope theo `appRoot/appHeader` giảm ảnh hưởng ngoài ý muốn đến widget WebEngine hoặc dialog khác.

```diff
+QLabel#statusBadge[statusState="ready"] { ... }
+QLabel#statusBadge[statusState="running"] { ... }
+QLabel#statusBadge[statusState="paused"] { ... }
+QLabel#statusBadge[statusState="finished"] { ... }
+QLabel#resultStatus[resultState="success"] { ... }
+QLabel#resultStatus[resultState="error"] { ... }
```

**Giải thích:** Qt dynamic property từ state machine điều khiển màu status/result. Một nguồn state cập nhật cả enabled state, text và visual, tránh handler tự set style rời rạc.

```diff
+QSplitter::handle { background: transparent; }
+QSplitter::handle:hover { background: #84adff; }
+QFrame#metricCard { ... }
+QTableWidget#routeTable { ... }
+QTextEdit#eventLog { ... }
```

**Giải thích:** Bổ sung style cho splitter có thể kéo, metric card, bảng route và Event Log mới. Spacing/height/input được chuẩn hóa để desktop và compact cùng một hệ thống.

### 8.2. `src/gui/themes/dark.qss`

```diff
-QMainWindow { background-color: #1e1e1e; color: #f0f0f0; }
+QWidget#appRoot { background: #101828; color: #f2f4f7; }
+QFrame#appHeader, QGroupBox, QFrame#metricCard { ... }
+QPushButton#primaryButton { background: #53b1fd; ... }
+QPushButton#secondaryButton { background: #1d2939; border-color: #475467; ... }
+QLabel#statusBadge[statusState="paused"] { ... }
```

**Giải thích:** Dark theme nhận cùng selector và semantics với light theme, chỉ đổi palette/contrast. Nhờ object name/dynamic property giống nhau, đổi theme không cần nhánh logic UI riêng. Map tile OSM vẫn sáng theo phạm vi đã chốt trong plan.

---

## 9. Regression tests

### 9.1. `tests/test_search_contract.py` — file mới

```diff
+def test_public_algorithms_use_the_visualization_contract():
+    algorithms = get_algorithms()
+    assert "Mock 3 Search" not in algorithms
+    assert "Uniform Cost Search (UCS)" in algorithms
+    for algorithm in algorithms:
+        result = run_algorithm(algorithm, graph, "A", "C")
+        assert isinstance(result, SearchResult)
+        assert result.success
+        assert result.to_dict()["steps"][-1]["type"] == "finish"
```

**Giải thích:** Khóa danh sách thuật toán công khai và contract event chung. Một thuật toán mới/đổi sau này phải trả SearchResult, path hợp lệ và FINISH thay vì làm renderer đoán format.

```diff
+def test_search_step_and_result_include_ui_metrics():
+    step = SearchStep(..., metrics={"g": 1, "h": 2, "f": 3},
+                      frontier=["B"], explored=["A"], visited_order=["A"])
+    result = SearchResult(..., runtime_ms=2.5,
+                          total_distance=1.0, estimated_time=2.0)
+    serialized = result.to_dict()
+    assert serialized["runtime_ms"] == 2.5
+    assert serialized["steps"][0]["metrics"]["f"] == 3.0
```

**Giải thích:** Test bảo đảm field model mới thực sự qua biên serialization tới JavaScript/UI và giữ kiểu dữ liệu mong đợi.

```diff
+def test_delta_steps_preserve_algorithm_selection_and_costs():
+    assert bfs_result.path == ["A", "B", "G"]
+    assert bfs_result.total_cost == 18.0
+    assert dfs_result.path == ["A", "C", "G"]
+    assert dfs_result.total_cost == 2.0
+    assert ucs_result.path == ["A", "C", "G"]
+    assert astar_result.path == ["A", "C", "G"]
```

**Giải thích:** Đây là regression quan trọng cho yêu cầu “không sửa logic cũ”. Việc đổi event delta/visited metadata không được đổi lựa chọn path hoặc cost của BFS/DFS/A*. UCS được khóa theo lowest-cost behavior.

```diff
+def test_core_search_events_do_not_retain_full_state_snapshots():
+    for algorithm in ("BFS", "DFS", "UCS", "A*"):
+        for step in result.steps:
+            assert step.frontier is None
+            assert step.explored is None
+            assert step.visited_order is None
```

**Giải thích:** Ngăn regression memory: core graph search phải tiếp tục phát delta compact, không vô tình quay lại copy full state ở từng step. GA được loại khỏi test này vì snapshot nhỏ là thiết kế có chủ đích.

```diff
+def test_graph_view_payload_deduplicates_visual_edges_without_losing_direction():
+    payload = GraphWidget._serialize_graph(graph)
+    assert len(payload["edges"]) == 1
+    assert {tuple(direction) for direction in edge["directions"]} == {
+        ("A", "B"), ("B", "A")
+    }
```

**Giải thích:** Khóa optimization physical-edge dedup đồng thời bảo đảm không mất hướng thuật toán. Nếu chỉ dedup mà bỏ directions, state inspect/path có thể tô sai cạnh.

---

## 10. Quan hệ giữa các thay đổi

```text
Algorithm (delta + metrics)
        │
        ▼
SearchResult / SearchStep
        │
        ▼
MapWidget playback controller
   ├── Map HTML renderer
   ├── GraphWidget → Graph HTML renderer
   ├── AlgorithmStatePanel
   └── MainWindow Event Log / Result Summary
```

**Giải thích:** Chỉ MapWidget sở hữu step index/timer. Bốn consumer nhận cùng event nên Map, Graph, State và Log không tạo logic search riêng. Đây là nguyên tắc kiến trúc chính giải thích phần lớn khác biệt với `develop`.

```text
Autoplay profile
   ├── Instant: xử lý state đầy đủ, map dựng final path một lần
   ├── Fast/Balanced/Detailed: backpressure + adaptive batch
   └── Step by step: không schedule timer, Next/Previous mỗi raw event
```

**Giải thích:** Step by step là nhánh điều phối playback mới, không thay adaptive cadence của bốn profile cũ và không thay kết quả thuật toán. Replay trong manual mode về step 0; Replay trong autoplay vẫn chạy lại.

## 11. Kết quả kiểm tra liên quan

| Kiểm tra | Kết quả hiện tại | Ý nghĩa |
| --- | --- | --- |
| `python -m compileall -q src` | Đạt | Toàn bộ Python source compile được. |
| `python -m pytest tests/test_search_contract.py -q` | `5 passed` | Contract/path/cost/payload mới không regression. |
| Manual playback smoke test | Đạt | Ở step 0 timer không active; Next/Previous đúng một step; Replay vẫn ở step 0. |
| Legacy autoplay smoke test | Đạt | Profile không manual vẫn tự chạy đến FINISH. |
| `git diff --check` trên file sửa | Đạt | Không có whitespace error trong patch. |

Full suite còn ba lỗi legacy đã có trước phần Step by step: một test dùng constructor `Node(x/y)` cũ và hai test cần `data/mock_data.json`, `data/map_data.json` không tồn tại. Các lỗi này không phát sinh từ redesign/playback.

## 12. Kết luận review

1. Khác biệt lớn nhất không nằm ở thuật toán tìm đường mà ở cách state được mô hình hóa, phát và render.
2. BFS/DFS/A* giữ logic chọn đường; event được chỉnh để phản ánh đúng queue/stack/priority và giảm memory. GA chỉ thêm guard chống treo. UCS là thuật toán công khai mới.
3. MainWindow chuyển từ tập handler enable/disable rời rạc sang execution state machine và worker thread.
4. MapWidget trở thành playback controller có backpressure; Map/Graph/State/Log là consumer của cùng event stream.
5. `Step by step · Manual` tắt timer bằng state/guard rõ ràng, không sửa cadence hay nhánh autoplay cũ.
6. Renderer và QSS được viết lại để hỗ trợ graph lớn, responsive layout, hai view và visual hierarchy trong `plan.md`.