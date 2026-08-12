import html
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.algorithms.algorithms import get_algorithms, run_algorithm
from src.data.data_loader import get_dataset_options, load_dataset
from src.gui.algorithm_state_panel import AlgorithmStatePanel
from src.gui.delivery_panel import ResultSummaryPanel
from src.gui.graph_widget import GraphWidget
from src.gui.map_widget import MapWidget


class SearchWorker(QObject):
    """Run a read-only graph search without blocking Qt's GUI thread."""

    completed = pyqtSignal(object, float)
    failed = pyqtSignal(str)

    def __init__(self, algorithm, graph, start_id, goal_id):
        super().__init__()
        self.algorithm = algorithm
        self.graph = graph
        self.start_id = start_id
        self.goal_id = goal_id

    @pyqtSlot()
    def run(self):
        try:
            started = time.perf_counter()
            result = run_algorithm(
                self.algorithm, self.graph, self.start_id, self.goal_id
            )
            runtime_ms = (time.perf_counter() - started) * 1000
            self.completed.emit(result, runtime_ms)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    """Responsive Map View for route-search algorithm visualization."""

    COMPACT_BREAKPOINT = 880
    EXECUTION_STATES = {
        "idle",
        "loading",
        "ready",
        "computing",
        "running",
        "paused",
        "finished",
    }

    def __init__(self):
        super().__init__()
        self.graph = None
        self.current_theme = "light"
        self.execution_state = "idle"
        self.delivery_nodes = []
        self._active_result = None
        self._active_algorithm = ""
        self._active_start = ""
        self._active_goal = ""
        self._compact_mode = False
        self._sidebar_user_collapsed = False
        self._state_user_collapsed = False
        self._sidebar_is_drawer = False
        self._search_thread = None
        self._search_worker = None
        self._node_model = None
        self._pending_load_summary = None
        self._pending_renderers = set()
        self._ready_renderers = set()
        self._active_view = "map"

        self.setup_window()
        self.build_ui()
        self.connect_signals()
        self.load_theme("light")
        self._set_execution_state("idle")
        self.result_panel.reset()
        self.algorithm_state.reset()
        self.log_event("INFO", "Application started. Load a dataset to begin.")
        QTimer.singleShot(0, self._apply_responsive_layout)

    def setup_window(self):
        self.setWindowTitle("Route Optimization Visualizer")
        self.resize(1280, 820)
        self.setMinimumSize(430, 620)

    def build_ui(self):
        self.central_widget = QWidget()
        self.central_widget.setObjectName("appRoot")
        self.setCentralWidget(self.central_widget)
        root = QVBoxLayout(self.central_widget)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

        root.addWidget(self.create_header())
        self.alert_banner = self.create_alert_banner()
        root.addWidget(self.alert_banner)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setObjectName("mainSplitter")
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(10)
        self.main_splitter.setOpaqueResize(True)

        self.sidebar_scroll = self.create_sidebar()
        self.workspace = self.create_workspace()
        self.main_splitter.addWidget(self.sidebar_scroll)
        self.main_splitter.addWidget(self.workspace)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([320, 940])
        root.addWidget(self.main_splitter, 1)

    def create_header(self):
        header = QFrame()
        header.setObjectName("appHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.sidebar_toggle = QPushButton("☰")
        self.sidebar_toggle.setObjectName("iconButton")
        self.sidebar_toggle.setAccessibleName("Toggle controls sidebar")
        self.sidebar_toggle.setToolTip("Show or hide route controls")
        layout.addWidget(self.sidebar_toggle)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        self.title_label = QLabel("Route Lab")
        self.title_label.setObjectName("appTitle")
        self.subtitle_label = QLabel("Map View · Single-route search")
        self.subtitle_label.setObjectName("appSubtitle")
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.subtitle_label)
        layout.addLayout(title_box)

        layout.addStretch()

        self.map_view_button = QPushButton("Map View")
        self.map_view_button.setObjectName("segmentButton")
        self.map_view_button.setCheckable(True)
        self.map_view_button.setChecked(True)
        self.graph_view_button = QPushButton("Graph View")
        self.graph_view_button.setObjectName("segmentButton")
        self.graph_view_button.setCheckable(True)
        self.graph_view_button.setToolTip("Show the node-edge graph renderer")
        layout.addWidget(self.map_view_button)
        layout.addWidget(self.graph_view_button)

        self.state_toggle = QPushButton("Hide state")
        self.state_toggle.setObjectName("tertiaryButton")
        layout.addWidget(self.state_toggle)

        self.status_badge = QLabel("Not ready")
        self.status_badge.setObjectName("statusBadge")
        layout.addWidget(self.status_badge)

        self.theme_button = QPushButton("Dark mode")
        self.theme_button.setObjectName("tertiaryButton")
        self.theme_button.setAccessibleName("Toggle light and dark theme")
        layout.addWidget(self.theme_button)
        return header

    def create_alert_banner(self):
        banner = QFrame()
        banner.setObjectName("alertBanner")
        banner.hide()
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(12, 8, 8, 8)
        self.alert_label = QLabel("")
        self.alert_label.setWordWrap(True)
        close_button = QPushButton("×")
        close_button.setObjectName("iconButton")
        close_button.setAccessibleName("Dismiss notification")
        close_button.clicked.connect(banner.hide)
        layout.addWidget(self.alert_label, 1)
        layout.addWidget(close_button)
        self.alert_timer = QTimer(self)
        self.alert_timer.setSingleShot(True)
        self.alert_timer.timeout.connect(banner.hide)
        return banner

    def create_sidebar(self):
        scroll = QScrollArea()
        scroll.setObjectName("sidebarScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(260)
        scroll.setMaximumWidth(520)
        scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        content = QWidget()
        content.setObjectName("sidebarContent")
        self.sidebar_content = content
        layout = QVBoxLayout(content)
        layout.setContentsMargins(6, 4, 8, 6)
        layout.setSpacing(10)

        layout.addWidget(self.create_dataset_group())
        layout.addWidget(self.create_algorithm_group())
        layout.addWidget(self.create_parameters_group())
        layout.addWidget(self.create_execution_group())
        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def create_dataset_group(self):
        group = QGroupBox("1 · Dataset")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.field_label("Area / network"))

        self.dataset_combo = QComboBox()
        self.dataset_combo.setObjectName("fieldInput")
        self.configure_resizable_combo(self.dataset_combo, 16)
        options = get_dataset_options()
        for option in options:
            label = self.friendly_dataset_name(option["filename"])
            if option["node_count"] is not None:
                label += f" · {option['node_count']} nodes"
            self.dataset_combo.addItem(label, option["filename"])
        if not options:
            self.dataset_combo.addItem("No JSON datasets found", None)
            self.dataset_combo.setEnabled(False)
        layout.addWidget(self.dataset_combo)

        self.load_button = QPushButton("Load graph data")
        self.load_button.setObjectName("secondaryButton")
        self.load_button.setEnabled(bool(options))
        layout.addWidget(self.load_button)

        self.graph_summary_label = QLabel("No graph loaded")
        self.graph_summary_label.setObjectName("mutedLabel")
        self.graph_summary_label.setWordWrap(True)
        layout.addWidget(self.graph_summary_label)
        return group

    def create_algorithm_group(self):
        group = QGroupBox("2 · Algorithm")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.field_label("Search strategy"))
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.setObjectName("fieldInput")
        self.configure_resizable_combo(self.algorithm_combo, 16)
        self.available_algorithms = get_algorithms()
        self.algorithm_combo.addItems(self.available_algorithms)
        if not self.available_algorithms:
            self.algorithm_combo.addItem("No algorithms available")
            self.algorithm_combo.setEnabled(False)
        layout.addWidget(self.algorithm_combo)
        self.algorithm_hint = QLabel("Frontier and explored state updates at every step.")
        self.algorithm_hint.setObjectName("mutedLabel")
        self.algorithm_hint.setWordWrap(True)
        layout.addWidget(self.algorithm_hint)
        return group

    def create_parameters_group(self):
        group = QGroupBox("3 · Route setup")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(self.field_label("Start location"))
        self.start_combo = self.searchable_combo()
        layout.addWidget(self.start_combo)

        layout.addWidget(self.field_label("Goal location"))
        self.goal_combo = self.searchable_combo()
        layout.addWidget(self.goal_combo)

        self.route_scope_label = QLabel(
            "Start–goal mode · input architecture is ready for future delivery stops."
        )
        self.route_scope_label.setObjectName("mutedLabel")
        self.route_scope_label.setWordWrap(True)
        layout.addWidget(self.route_scope_label)

        layout.addWidget(self.field_label("Autoplay speed"))
        self.speed_combo = QComboBox()
        self.speed_combo.setObjectName("fieldInput")
        self.configure_resizable_combo(self.speed_combo, 14)
        for label, profile in (
            (
                "Instant",
                {
                    "name": "Instant",
                    "interval_ms": 0,
                    "target_duration_ms": 0,
                    "hint": "Show the final route immediately without intermediate map frames.",
                },
            ),
            (
                "Fast · ~5 s",
                {
                    "name": "Fast",
                    "interval_ms": 50,
                    "target_duration_ms": 5000,
                    "hint": "Fast overview; large searches target roughly 5 seconds.",
                },
            ),
            (
                "Balanced · ~15 s",
                {
                    "name": "Balanced",
                    "interval_ms": 100,
                    "target_duration_ms": 15000,
                    "hint": "Recommended balance; large searches target roughly 15 seconds.",
                },
            ),
            (
                "Detailed · ~30 s",
                {
                    "name": "Detailed",
                    "interval_ms": 200,
                    "target_duration_ms": 30000,
                    "hint": "Slower inspection; large searches target roughly 30 seconds.",
                },
            ),
            (
                "Step by step · Manual",
                {
                    "name": "Step by step",
                    "interval_ms": 100,
                    "target_duration_ms": 0,
                    "manual": True,
                    "hint": "Manual playback only; use Previous and Next to move one event at a time.",
                },
            ),
        ):
            self.speed_combo.addItem(label, profile)
        self.speed_combo.setCurrentIndex(2)
        layout.addWidget(self.speed_combo)
        self.speed_hint = QLabel("")
        self.speed_hint.setObjectName("mutedLabel")
        self.speed_hint.setWordWrap(True)
        layout.addWidget(self.speed_hint)
        self._update_speed_hint()
        return group

    def create_execution_group(self):
        group = QGroupBox("4 · Playback")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)

        self.run_button = QPushButton("Run search")
        self.run_button.setObjectName("primaryButton")
        layout.addWidget(self.run_button)

        grid = QGridLayout()
        grid.setSpacing(7)
        self.pause_button = QPushButton("Pause")
        self.previous_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")
        self.replay_button = QPushButton("Replay")
        self.reset_button = QPushButton("Reset")
        for button in (
            self.pause_button,
            self.previous_button,
            self.next_button,
            self.replay_button,
            self.reset_button,
        ):
            button.setObjectName("secondaryButton")
        grid.addWidget(self.pause_button, 0, 0, 1, 2)
        grid.addWidget(self.previous_button, 1, 0)
        grid.addWidget(self.next_button, 1, 1)
        grid.addWidget(self.replay_button, 2, 0)
        grid.addWidget(self.reset_button, 2, 1)
        layout.addLayout(grid)
        return group

    def create_workspace(self):
        workspace = QWidget()
        workspace.setObjectName("workspace")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.workspace_splitter = QSplitter(Qt.Vertical)
        self.workspace_splitter.setObjectName("workspaceSplitter")
        self.workspace_splitter.setChildrenCollapsible(False)

        self.visualization_splitter = QSplitter(Qt.Horizontal)
        self.visualization_splitter.setObjectName("visualizationSplitter")
        self.visualization_splitter.setChildrenCollapsible(False)
        self.visualization_splitter.setHandleWidth(10)
        self.visualization_splitter.setOpaqueResize(True)
        self.map_widget = MapWidget()
        self.graph_widget = GraphWidget()
        self.graph_widget.set_render_enabled(False)
        self.visualization_stack = QStackedWidget()
        self.visualization_stack.setObjectName("visualizationStack")
        self.visualization_stack.addWidget(self.map_widget)
        self.visualization_stack.addWidget(self.graph_widget)
        self.visualization_stack.setCurrentWidget(self.map_widget)
        self.algorithm_state = AlgorithmStatePanel()
        self.visualization_splitter.addWidget(self.visualization_stack)
        self.visualization_splitter.addWidget(self.algorithm_state)
        self.visualization_splitter.setStretchFactor(0, 3)
        self.visualization_splitter.setStretchFactor(1, 1)
        self.visualization_splitter.setSizes([720, 330])

        self.info_tabs = QTabWidget()
        self.info_tabs.setObjectName("infoTabs")
        self.info_tabs.setDocumentMode(True)

        self.result_panel = ResultSummaryPanel()
        self.result_scroll = QScrollArea()
        self.result_scroll.setObjectName("resultScroll")
        self.result_scroll.setWidgetResizable(True)
        self.result_scroll.setFrameShape(QFrame.NoFrame)
        self.result_scroll.setWidget(self.result_panel)
        self.info_tabs.addTab(self.result_scroll, "Result")

        self.event_log = QTextEdit()
        self.event_log.setObjectName("eventLog")
        self.event_log.setReadOnly(True)
        self.event_log.document().setMaximumBlockCount(1200)
        self.info_tabs.addTab(self.event_log, "Event log")

        comparison = QWidget()
        comparison_layout = QVBoxLayout(comparison)
        comparison_layout.setContentsMargins(24, 20, 24, 20)
        comparison_title = QLabel("Comparison View")
        comparison_title.setObjectName("panelTitle")
        comparison_text = QLabel(
            "Coming soon · Single-run metrics and playback are completed first. "
            "The future table will compare runs using the same dataset, route, "
            "cost function and conditions."
        )
        comparison_text.setObjectName("mutedLabel")
        comparison_text.setWordWrap(True)
        comparison_layout.addWidget(comparison_title)
        comparison_layout.addWidget(comparison_text)
        comparison_layout.addStretch()
        self.info_tabs.addTab(comparison, "Comparison · Soon")

        self.workspace_splitter.addWidget(self.visualization_splitter)
        self.workspace_splitter.addWidget(self.info_tabs)
        self.workspace_splitter.setStretchFactor(0, 4)
        self.workspace_splitter.setStretchFactor(1, 1)
        self.workspace_splitter.setSizes([600, 185])
        layout.addWidget(self.workspace_splitter)
        return workspace

    def connect_signals(self):
        self.load_button.clicked.connect(self.on_load_graph_clicked)
        self.algorithm_combo.currentTextChanged.connect(self.on_algorithm_changed)
        self.start_combo.currentIndexChanged.connect(self.on_start_changed)
        self.goal_combo.currentIndexChanged.connect(self.on_goal_changed)
        self.speed_combo.currentIndexChanged.connect(self.on_speed_changed)

        self.run_button.clicked.connect(self.on_run_search_clicked)
        self.pause_button.clicked.connect(self.on_pause_resume_clicked)
        self.previous_button.clicked.connect(self.on_previous_clicked)
        self.next_button.clicked.connect(self.on_next_clicked)
        self.replay_button.clicked.connect(self.on_replay_clicked)
        self.reset_button.clicked.connect(self.on_reset_clicked)

        self.map_widget.animation_finished.connect(self.on_animation_finished)
        self.map_widget.step_changed.connect(self.on_step_changed)
        self.map_widget.playback_state_changed.connect(self.on_playback_state_changed)
        self.map_widget.graph_ready.connect(
            lambda: self.on_visualization_render_ready("map")
        )
        self.map_widget.graph_render_failed.connect(
            lambda message: self.on_visualization_render_failed("map", message)
        )
        self.graph_widget.graph_ready.connect(
            lambda: self.on_visualization_render_ready("graph")
        )
        self.graph_widget.graph_render_failed.connect(
            lambda message: self.on_visualization_render_failed("graph", message)
        )

        self.sidebar_toggle.clicked.connect(self.toggle_sidebar)
        self.state_toggle.clicked.connect(self.toggle_state_panel)
        self.algorithm_state.collapse_requested.connect(self.toggle_state_panel)
        self.theme_button.clicked.connect(self.toggle_theme)
        self.graph_view_button.clicked.connect(self.on_graph_view_clicked)
        self.map_view_button.clicked.connect(self.on_map_view_clicked)

    @staticmethod
    def field_label(text):
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    @staticmethod
    def searchable_combo():
        combo = QComboBox()
        combo.setObjectName("fieldInput")
        MainWindow.configure_resizable_combo(combo, 14)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        completer = combo.completer()
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        return combo

    @staticmethod
    def configure_resizable_combo(combo, minimum_characters=14):
        """Allow combo boxes to shrink and grow with the draggable sidebar."""
        combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(minimum_characters)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    @staticmethod
    def friendly_dataset_name(filename):
        stem = Path(filename).stem.strip("_").lower()
        if stem == "map_data":
            return "HCMC sample network"
        stem = re.sub(r"^map_", "", stem)
        words = stem.replace("_", " ").title()
        return words.replace("District ", "District ")

    @staticmethod
    def natural_node_key(node_id):
        return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", node_id)]

    def current_start_id(self):
        return self.start_combo.currentData() or ""

    def current_goal_id(self):
        return self.goal_combo.currentData() or ""

    def route_request(self):
        return {
            "start_node": self.current_start_id(),
            "delivery_nodes": list(self.delivery_nodes),
        }

    def on_load_graph_clicked(self):
        filename = self.dataset_combo.currentData()
        if not filename:
            self.show_alert("No dataset is available to load.", "error")
            return

        self._set_execution_state("loading")
        QApplication.processEvents()
        try:
            self.graph = load_dataset(filename)
            self._pending_renderers = {"map", "graph"}
            self._ready_renderers.clear()
            self.map_widget.draw_graph(self.graph)
            self.graph_widget.draw_graph(self.graph)
            node_ids = sorted(self.graph.nodes, key=self.natural_node_key)
            self._populate_node_combos(node_ids)

            self.on_start_changed(self.start_combo.currentIndex())
            self.on_goal_changed(self.goal_combo.currentIndex())
            edge_count = sum(len(edges) for edges in self.graph.adjacency_list.values())
            self.graph_summary_label.setText(
                f"{len(node_ids)} nodes · {edge_count} directed edges"
            )
            self.result_panel.reset("Single-route search")
            self.algorithm_state.reset()
            self.algorithm_state.set_algorithm(self.algorithm_combo.currentText())
            self._active_result = None
            self.map_widget.show_message(
                "Rendering graph layers. Controls will unlock when the map is ready.",
                "info",
            )
            self._pending_load_summary = (
                filename,
                len(node_ids),
                edge_count,
            )
            self.log_event("INFO", f"Loaded {filename}; rendering map layers in batches.")
            if self._compact_mode:
                self.sidebar_scroll.hide()
        except Exception as exc:
            self._pending_load_summary = None
            self._set_execution_state("idle")
            self.show_alert(f"Failed to load graph: {exc}", "error")
            self.map_widget.show_message("Graph data could not be loaded.", "error")
            self.log_event("ERROR", f"Failed to load {filename}: {exc}")

    def _populate_node_combos(self, node_ids):
        """Populate both selectors from one batch-built shared item model."""
        model = QStandardItemModel(self)
        items = []
        for node_id in node_ids:
            node = self.graph.nodes[node_id]
            item = QStandardItem(f"{node.id} — {node.name}")
            item.setData(node.id, Qt.UserRole)
            items.append(item)
        if items:
            model.invisibleRootItem().appendRows(items)

        self.start_combo.blockSignals(True)
        self.goal_combo.blockSignals(True)
        self.start_combo.setModel(model)
        self.goal_combo.setModel(model)
        if node_ids:
            self.start_combo.setCurrentIndex(0)
            self.goal_combo.setCurrentIndex(len(node_ids) - 1)
        self.start_combo.blockSignals(False)
        self.goal_combo.blockSignals(False)

        old_model = self._node_model
        self._node_model = model
        if old_model is not None:
            old_model.deleteLater()

    def on_visualization_render_ready(self, renderer):
        if self.graph is None:
            return
        self._pending_renderers.discard(renderer)
        self._ready_renderers.add(renderer)
        if (
            self.execution_state != "loading"
            or self._active_view not in self._ready_renderers
        ):
            return
        self._finish_visualization_load()

    def _finish_visualization_load(self):
        self._set_execution_state("ready")
        self.map_widget.show_message(
            "Graph ready. Select start, goal and algorithm, then run.", "success"
        )
        if self._pending_load_summary is not None:
            filename, node_count, edge_count = self._pending_load_summary
            self.show_alert(
                f"Loaded {self.friendly_dataset_name(filename)} successfully.",
                "success",
            )
            self.log_event(
                "SUCCESS",
                f"Rendered {filename}: {node_count} nodes, "
                f"{edge_count} directed edges.",
            )
        self._pending_load_summary = None

    def on_visualization_render_failed(self, renderer, message):
        self._pending_renderers.discard(renderer)
        self._ready_renderers.discard(renderer)
        title = "Map" if renderer == "map" else "Graph"
        if renderer != self._active_view:
            self.show_alert(
                f"{title} View could not be prepared; the active view is still usable.",
                "warning",
            )
            self.log_event("WARNING", f"{title} rendering failed: {message}")
            if (
                self.execution_state == "loading"
                and self._active_view in self._ready_renderers
            ):
                self._finish_visualization_load()
            return

        self._pending_load_summary = None
        self._set_execution_state("idle")
        self.show_alert(f"{title} rendering failed: {message}", "error")
        self.log_event("ERROR", f"{title} rendering failed: {message}")

    def on_run_search_clicked(self):
        if self.graph is None:
            self.show_alert("Load a dataset before running a search.", "error")
            return
        if self._active_view not in self._ready_renderers:
            title = "Graph" if self._active_view == "graph" else "Map"
            self.show_alert(f"{title} View is still rendering. Please wait.", "warning")
            return

        start_id = self.current_start_id()
        goal_id = self.current_goal_id()
        algorithm = self.algorithm_combo.currentText()
        if not start_id or not goal_id or not algorithm:
            self.show_alert("Choose a valid start, goal and algorithm.", "error")
            return

        self._active_algorithm = algorithm
        self._active_start = start_id
        self._active_goal = goal_id
        self._set_execution_state("computing")
        QApplication.processEvents()

        self.map_widget.reset(emit_state=False)
        self.graph_widget.reset_visualization()
        self.algorithm_state.reset()
        self.algorithm_state.set_algorithm(algorithm)
        self.result_panel.set_running(algorithm, start_id, goal_id)
        self.log_event("INFO", f"Running {algorithm}: {start_id} → {goal_id}.")

        self._search_thread = QThread(self)
        self._search_worker = SearchWorker(
            algorithm, self.graph, start_id, goal_id
        )
        self._search_worker.moveToThread(self._search_thread)
        self._search_thread.started.connect(self._search_worker.run)
        self._search_worker.completed.connect(self._on_search_completed)
        self._search_worker.failed.connect(self._on_search_failed)
        self._search_worker.completed.connect(self._search_thread.quit)
        self._search_worker.failed.connect(self._search_thread.quit)
        self._search_worker.completed.connect(self._search_worker.deleteLater)
        self._search_worker.failed.connect(self._search_worker.deleteLater)
        self._search_thread.finished.connect(self._on_search_thread_finished)
        self._search_thread.finished.connect(self._search_thread.deleteLater)
        self._search_thread.start()

    def _on_search_completed(self, result, runtime_ms):
        result.runtime_ms = runtime_ms
        self._enrich_result_metrics(result)
        self._active_result = result
        profile = self.current_playback_profile()
        manual_mode = profile.get("manual", False)
        self._set_execution_state("paused" if manual_mode else "running")
        self.map_widget.draw_map_step_by_step(
            result,
            profile["interval_ms"],
            profile["target_duration_ms"],
            manual_mode=manual_mode,
        )
        if manual_mode:
            self.map_widget.show_message(
                f"{self._active_algorithm} ready · use Previous/Next for each step"
            )
        else:
            self.map_widget.show_message(
                f"Running {self._active_algorithm} · {profile['name']}"
            )
        if self._compact_mode:
            self.sidebar_scroll.hide()

    def _on_search_failed(self, message):
        self._active_result = None
        self._set_execution_state("ready")
        self.show_alert(f"Search failed: {message}", "error")
        self.log_event("ERROR", f"{self._active_algorithm} failed: {message}")

    def _on_search_thread_finished(self):
        self._search_worker = None
        self._search_thread = None

    def _enrich_result_metrics(self, result):
        distance = 0.0
        estimated_time = 0.0
        complete = bool(result.path)
        route_details = []
        for from_node, to_node in zip(result.path, result.path[1:]):
            edge = self.graph.get_edge(from_node, to_node)
            if edge is None:
                complete = False
                break
            distance += edge.distance
            estimated_time += edge.travel_time
            route_details.append(
                {
                    "from": from_node,
                    "to": to_node,
                    "distance": edge.distance,
                    "travel_time": edge.travel_time,
                    "road": edge.note or edge.road_type,
                }
            )
        result.total_distance = distance if complete else None
        result.estimated_time = estimated_time if complete else None
        result.route_details = route_details if complete else []

    def on_pause_resume_clicked(self):
        if self.current_playback_profile().get("manual", False):
            return
        if self.execution_state == "running":
            self.map_widget.pause_animation()
            self.log_event("INFO", "Playback paused.")
        elif self.execution_state == "paused":
            self.map_widget.resume_animation()
            self.log_event("INFO", "Playback resumed.")

    def on_previous_clicked(self):
        self.map_widget.previous_step()
        if self.map_widget.step_index < self.map_widget.step_count:
            self._set_execution_state("paused")
        self.log_event("INFO", "Moved to the previous playback step.")

    def on_next_clicked(self):
        self.map_widget.next_step()
        if self.map_widget.step_index < self.map_widget.step_count:
            self._set_execution_state("paused")
        self.log_event("INFO", "Advanced one playback step.")

    def on_replay_clicked(self):
        if self._active_result is None:
            return
        self.algorithm_state.reset()
        self.graph_widget.reset_visualization()
        self.result_panel.set_running(
            self._active_algorithm, self._active_start, self._active_goal
        )
        self.map_widget.replay_animation()
        if self.current_playback_profile().get("manual", False):
            self._set_execution_state("paused")
            self.log_event("INFO", "Manual playback returned to the initial state.")
        else:
            self._set_execution_state("running")
            self.log_event("INFO", "Playback restarted from step 1.")

    def on_reset_clicked(self):
        self.map_widget.reset()
        self.graph_widget.reset_visualization()
        self.algorithm_state.reset()
        self.result_panel.reset("Single-route search")
        self._active_result = None
        self._set_execution_state("ready" if self.graph is not None else "idle")
        self.log_event("INFO", "Visualization reset; graph and route selection preserved.")

    def on_animation_finished(self):
        self._set_execution_state("finished")
        if self._active_result is None:
            return
        self.result_panel.set_result(
            self._active_result,
            self._active_algorithm,
            self._active_start,
            self._active_goal,
        )
        self.info_tabs.setCurrentWidget(self.result_scroll)
        if self._active_result.success:
            self.map_widget.show_message("Search completed · final path highlighted", "success")
            self.show_alert("Search completed and a route was found.", "success")
            self.log_event(
                "SUCCESS",
                f"Completed in {self._active_result.runtime_ms:.2f} ms; "
                f"visited {len(self._active_result.visited_order)} nodes.",
            )
        else:
            self.map_widget.show_message("Search completed · no route found", "error")
            self.show_alert(self._active_result.message or "No route was found.", "error")
            self.log_event("ERROR", self._active_result.message or "No route was found.")

    def on_step_changed(self, step):
        self.graph_widget.apply_playback_event(step)
        self.algorithm_state.update_step(step)
        event_type = step.get("type", "unknown").upper()
        index = step.get("_index", 0)
        total = step.get("_total", 0)
        node = step.get("node")
        if event_type == "EXPAND":
            detail = f"expand {node}"
        elif event_type in {"DISCOVER", "UPDATE"}:
            detail = f"{event_type.lower()} {step.get('from')} → {step.get('to')}"
        elif event_type == "FINISH":
            detail = "finish search"
        elif event_type == "RESET":
            detail = "return to initial state"
        else:
            detail = event_type.lower()
        batch_size = int(step.get("_batch_size", 1))
        if batch_size > 1:
            detail = f"processed {batch_size} events · latest: {detail}"
        self.log_event("STEP", f"{index}/{total} · {detail}.")
        self._refresh_playback_buttons()

    def on_playback_state_changed(self, state):
        if state in self.EXECUTION_STATES:
            self._set_execution_state(state)

    def on_algorithm_changed(self, algorithm):
        if hasattr(self, "algorithm_state"):
            self.algorithm_state.set_algorithm(algorithm)
        if self.graph is not None and self.execution_state not in {"running", "paused"}:
            self._set_execution_state("ready")

    def on_start_changed(self, _index):
        node_id = self.current_start_id()
        if node_id:
            self.map_widget.set_start_node(node_id)
            self.graph_widget.set_start_node(node_id)
            if self.graph is not None:
                self.log_event("INFO", f"Start location: {node_id}.")

    def on_goal_changed(self, _index):
        node_id = self.current_goal_id()
        self.delivery_nodes = [node_id] if node_id else []
        if node_id:
            self.map_widget.set_goal_node(node_id)
            self.graph_widget.set_goal_node(node_id)
            if self.graph is not None:
                self.log_event("INFO", f"Goal location: {node_id}.")

    def on_speed_changed(self, _index):
        profile = self.current_playback_profile()
        self._update_speed_hint()
        self.map_widget.set_playback_profile(
            profile["interval_ms"],
            profile["target_duration_ms"],
            manual_mode=profile.get("manual", False),
        )
        self._set_execution_state(self.execution_state)
        if self.execution_state in {"running", "paused"}:
            if profile.get("manual", False):
                self.log_event(
                    "INFO",
                    "Step-by-step mode enabled; autoplay is off.",
                )
            else:
                self.log_event(
                    "INFO",
                    f"Playback speed changed to {profile['name']} "
                    f"(target ~{profile['target_duration_ms'] / 1000:.0f} s for large searches).",
                )

    def current_playback_profile(self):
        profile = self.speed_combo.currentData()
        if isinstance(profile, dict):
            return profile
        return {
            "name": "Balanced",
            "interval_ms": 100,
            "target_duration_ms": 15000,
            "manual": False,
            "hint": "Recommended balanced playback.",
        }

    def _update_speed_hint(self):
        if not hasattr(self, "speed_hint"):
            return
        profile = self.current_playback_profile()
        if profile.get("manual", False):
            suffix = " Autoplay stays off until another speed is selected."
        else:
            suffix = (
                " Large searches group adjacent events; Previous/Next still move one event."
                if profile["interval_ms"] > 0
                else " Algorithm State and results remain complete."
            )
        self.speed_hint.setText(profile.get("hint", "") + suffix)

    def on_graph_view_clicked(self):
        self._set_visualization_mode("graph")

    def on_map_view_clicked(self):
        self._set_visualization_mode("map")

    def _set_visualization_mode(self, mode):
        mode = "graph" if mode == "graph" else "map"
        changed = mode != self._active_view
        self._active_view = mode
        graph_active = mode == "graph"
        self.visualization_stack.setCurrentWidget(
            self.graph_widget if graph_active else self.map_widget
        )
        self.graph_view_button.setChecked(graph_active)
        self.map_view_button.setChecked(not graph_active)
        self.map_widget.set_visual_updates_enabled(not graph_active)
        self.graph_widget.set_render_enabled(graph_active)
        self.subtitle_label.setText(
            "Graph View · Node-edge search"
            if graph_active
            else "Map View · Single-route search"
        )
        if changed:
            self.log_event(
                "INFO",
                "Switched to Graph View."
                if graph_active
                else "Switched to Map View.",
            )
        if (
            self.execution_state == "loading"
            and self.graph is not None
            and mode in self._ready_renderers
        ):
            self._finish_visualization_load()

    def _set_execution_state(self, state):
        if state not in self.EXECUTION_STATES:
            return
        self.execution_state = state
        manual_mode = self.current_playback_profile().get("manual", False)
        self.run_button.setEnabled(state in {"ready", "finished"})
        self.pause_button.setEnabled(
            not manual_mode and state in {"running", "paused"}
        )
        if manual_mode:
            self.pause_button.setText("Manual mode")
        else:
            self.pause_button.setText("Resume" if state == "paused" else "Pause")
        self.replay_button.setEnabled(state in {"paused", "finished"} and self._active_result is not None)
        self.reset_button.setEnabled(
            state not in {"idle", "loading", "computing"}
        )
        self._refresh_playback_buttons()

        controls_locked = state in {"loading", "computing", "running", "paused"}
        self.dataset_combo.setEnabled(not controls_locked)
        self.load_button.setEnabled(
            not controls_locked and self.dataset_combo.currentData() is not None
        )
        self.algorithm_combo.setEnabled(
            not controls_locked and bool(self.available_algorithms)
        )
        route_enabled = not controls_locked and self.graph is not None
        self.start_combo.setEnabled(route_enabled)
        self.goal_combo.setEnabled(route_enabled)
        self.speed_combo.setEnabled(state not in {"loading", "computing"})

        labels = {
            "idle": ("Not ready", "idle"),
            "loading": ("Rendering", "running"),
            "ready": ("Ready", "ready"),
            "computing": ("Computing", "running"),
            "running": ("Running", "running"),
            "paused": ("Paused", "paused"),
            "finished": ("Finished", "finished"),
        }
        if manual_mode and state == "paused":
            labels["paused"] = ("Manual", "paused")
        self._set_status_badge(*labels[state])

    def _refresh_playback_buttons(self):
        has_steps = self.map_widget.step_count > 0
        can_navigate = self.execution_state in {"running", "paused", "finished"}
        self.previous_button.setEnabled(
            has_steps and can_navigate and self.map_widget.step_index > 0
        )
        self.next_button.setEnabled(
            has_steps
            and self.execution_state in {"running", "paused"}
            and self.map_widget.step_index < self.map_widget.step_count
        )

    def _set_status_badge(self, text, state):
        self.status_badge.setText(text)
        self.status_badge.setProperty("statusState", state)
        self._refresh_style(self.status_badge)

    def toggle_sidebar(self):
        if self._compact_mode:
            if self.sidebar_scroll.isVisible():
                self.sidebar_scroll.hide()
            else:
                self._position_sidebar_drawer()
                self.sidebar_scroll.show()
                self.sidebar_scroll.raise_()
            return

        self._sidebar_user_collapsed = self.sidebar_scroll.isVisible()
        self.sidebar_scroll.setVisible(not self._sidebar_user_collapsed)

    def toggle_state_panel(self):
        if self._compact_mode:
            self.info_tabs.setCurrentWidget(self.result_scroll)
            return
        visible = self.algorithm_state.isVisible()
        self._state_user_collapsed = visible
        self.algorithm_state.setVisible(not visible)
        self.state_toggle.setText("Show state" if visible else "Hide state")
        if not visible:
            if self.visualization_splitter.orientation() == Qt.Horizontal:
                self.visualization_splitter.setSizes([720, 330])
            else:
                self.visualization_splitter.setSizes([430, 190])

    def toggle_theme(self):
        self.load_theme("dark" if self.current_theme == "light" else "light")

    def load_theme(self, theme_name):
        theme_path = Path(__file__).resolve().parent / "themes" / f"{theme_name}.qss"
        try:
            with open(theme_path, encoding="utf-8") as file:
                self.setStyleSheet(file.read())
            self.current_theme = theme_name
            self.theme_button.setText(
                "◐" if self._compact_mode else (
                    "Light mode" if theme_name == "dark" else "Dark mode"
                )
            )
            if hasattr(self, "map_widget"):
                self.map_widget.set_theme(theme_name)
            if hasattr(self, "graph_widget"):
                self.graph_widget.set_theme(theme_name)
        except OSError as exc:
            self.log_event("ERROR", f"Could not load {theme_name} theme: {exc}")

    def show_alert(self, message, level="info"):
        self.alert_label.setText(message)
        self.alert_banner.setProperty("alertLevel", level)
        self._refresh_style(self.alert_banner)
        self.alert_banner.show()
        self.alert_timer.start(7000 if level == "error" else 4500)

    def log_event(self, level, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "INFO": "#3b82f6",
            "SUCCESS": "#16a34a",
            "ERROR": "#ef4444",
            "STEP": "#8b5cf6",
        }
        color = colors.get(level, "#64748b")
        self.event_log.append(
            f'<span style="color:#64748b">[{timestamp}]</span> '
            f'<span style="color:{color};font-weight:700">'
            f'[{html.escape(level)}]</span> '
            f'<span>{html.escape(str(message))}</span>'
        )
        scrollbar = self.event_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._apply_responsive_layout)

    def _apply_responsive_layout(self):
        compact = self.width() < self.COMPACT_BREAKPOINT
        if compact != self._compact_mode:
            self._compact_mode = compact
            if compact:
                self._enter_compact_layout()
            else:
                self._exit_compact_layout()

        self.subtitle_label.setVisible(self.width() >= 650)
        self.graph_view_button.setVisible(self.width() >= 720)
        self.map_view_button.setVisible(self.width() >= 720)
        self.state_toggle.setVisible(self.width() >= 560)
        self.result_panel.set_compact(self.width() < 720)
        self.theme_button.setText(
            ("◐" if self._compact_mode else "Light mode")
            if self.current_theme == "dark"
            else ("◐" if self._compact_mode else "Dark mode")
        )
        self.theme_button.setToolTip(
            "Switch to light mode" if self.current_theme == "dark" else "Switch to dark mode"
        )
        if self._compact_mode:
            self._position_sidebar_drawer()

    def _enter_compact_layout(self):
        self.sidebar_scroll.hide()
        self.sidebar_scroll.setParent(self.central_widget)
        self._sidebar_is_drawer = True
        self.algorithm_state.setParent(self.info_tabs)
        self.info_tabs.insertTab(0, self.algorithm_state, "State")
        self.info_tabs.setTabText(self.info_tabs.indexOf(self.event_log), "Log")
        self.info_tabs.setTabText(self.info_tabs.count() - 1, "Compare")
        self.visualization_splitter.setOrientation(Qt.Horizontal)
        self.algorithm_state.setMaximumWidth(16777215)
        self.algorithm_state.setVisible(not self._state_user_collapsed)
        self.algorithm_state.collapse_button.setText("Result")
        self.workspace_splitter.setSizes([330, 240])

    def _exit_compact_layout(self):
        self.sidebar_scroll.hide()
        self.main_splitter.insertWidget(0, self.sidebar_scroll)
        self._sidebar_is_drawer = False
        self.sidebar_scroll.setVisible(not self._sidebar_user_collapsed)
        state_index = self.info_tabs.indexOf(self.algorithm_state)
        if state_index >= 0:
            self.info_tabs.removeTab(state_index)
        self.visualization_splitter.addWidget(self.algorithm_state)
        self.info_tabs.setTabText(self.info_tabs.indexOf(self.event_log), "Event log")
        self.info_tabs.setTabText(self.info_tabs.count() - 1, "Comparison · Soon")
        self.visualization_splitter.setOrientation(Qt.Horizontal)
        self.algorithm_state.setMaximumWidth(680)
        self.algorithm_state.setVisible(not self._state_user_collapsed)
        self.algorithm_state.collapse_button.setText("Hide")
        self.visualization_splitter.setSizes([720, 330])
        self.workspace_splitter.setSizes([600, 185])
        self.main_splitter.setSizes([320, max(500, self.width() - 354)])

    def _position_sidebar_drawer(self):
        if not self._sidebar_is_drawer:
            return
        header_bottom = self.sidebar_toggle.parentWidget().geometry().bottom() + 18
        width = min(304, max(260, self.central_widget.width() - 24))
        height = max(300, self.central_widget.height() - header_bottom - 12)
        self.sidebar_scroll.setGeometry(12, header_bottom, width, height)

    @staticmethod
    def _refresh_style(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Route Optimization Visualizer")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
