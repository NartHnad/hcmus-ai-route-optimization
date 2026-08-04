from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.models.models import ComparisonMode


class MetricCard(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        self.value_label = QLabel("—")
        self.value_label.setObjectName("metricValue")
        self.value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value):
        self.value_label.setText(str(value))


class ResultSummaryPanel(QGroupBox):
    """Single source of truth for the current run result."""

    def __init__(self, parent=None):
        super().__init__("Result summary", parent)
        self.setObjectName("resultSummary")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(10)

        heading_row = QHBoxLayout()
        self.status_label = QLabel("No run yet")
        self.status_label.setObjectName("resultStatus")
        self.context_label = QLabel("Single-route search")
        self.context_label.setObjectName("mutedLabel")
        heading_row.addWidget(self.status_label)
        heading_row.addStretch()
        heading_row.addWidget(self.context_label)
        layout.addLayout(heading_row)

        self.metrics_layout = QGridLayout()
        self.metrics_layout.setContentsMargins(0, 0, 0, 0)
        self.metrics_layout.setHorizontalSpacing(8)
        self.metrics_layout.setVerticalSpacing(8)
        self.distance = MetricCard("Distance")
        self.runtime = MetricCard("Runtime")
        self.visited = MetricCard("Visited nodes")
        self.cost = MetricCard("Path cost")
        self.estimated_time = MetricCard("Estimated time")
        self.metric_cards = [
            self.distance,
            self.runtime,
            self.visited,
            self.cost,
            self.estimated_time,
        ]
        self.set_compact(False)
        layout.addLayout(self.metrics_layout)

        self.route_label = QLabel("Route: —")
        self.route_label.setObjectName("routeText")
        self.route_label.setWordWrap(True)
        self.route_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.route_label)

        self.route_table = QTableWidget(0, 4)
        self.route_table.setObjectName("routeTable")
        self.route_table.setHorizontalHeaderLabels(
            ["Segment", "Distance", "Time", "Road"]
        )
        self.route_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.route_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.route_table.verticalHeader().hide()
        self.route_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.route_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.route_table.setAlternatingRowColors(True)
        self.route_table.setMaximumHeight(150)
        self.route_table.hide()
        layout.addWidget(self.route_table)

        self.message_label = QLabel("Load a dataset and run an algorithm to see metrics.")
        self.message_label.setObjectName("mutedLabel")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

    def reset(self, context="Single-route search"):
        self.status_label.setText("No run yet")
        self.status_label.setProperty("resultState", "idle")
        self.context_label.setText(context)
        for card in (
            self.distance,
            self.runtime,
            self.visited,
            self.cost,
            self.estimated_time,
        ):
            card.set_value("—")
        self.route_label.setText("Route: —")
        self.route_table.setRowCount(0)
        self.route_table.hide()
        self.message_label.setText("Run an algorithm to see its result.")
        self._refresh_style(self.status_label)

    def set_running(self, algorithm, start, goal):
        self.status_label.setText("Running")
        self.status_label.setProperty("resultState", "running")
        self.context_label.setText(f"{algorithm} · {start} → {goal}")
        self.message_label.setText("Result metrics will appear when playback finishes.")
        self._refresh_style(self.status_label)

    def set_result(self, result, algorithm, start, goal):
        success = bool(getattr(result, "success", False))
        self.status_label.setText("Route found" if success else "No route found")
        self.status_label.setProperty("resultState", "success" if success else "error")
        self.context_label.setText(f"{algorithm} · {start} → {goal}")

        distance = getattr(result, "total_distance", None)
        estimated = getattr(result, "estimated_time", None)
        self.distance.set_value("—" if distance is None else f"{distance:.2f} km")
        self.runtime.set_value(f"{getattr(result, 'runtime_ms', 0.0):.2f} ms")
        self.visited.set_value(len(getattr(result, "visited_order", []) or []))
        self.cost.set_value(f"{getattr(result, 'total_cost', 0.0):,.2f}")
        self.estimated_time.set_value(
            "—" if estimated is None else f"{estimated:.1f} min"
        )

        path = list(getattr(result, "path", []) or [])
        self.route_label.setText("Route: " + (" → ".join(path) if path else "—"))
        route_details = list(getattr(result, "route_details", []) or [])
        self.route_table.setRowCount(len(route_details))
        for row, detail in enumerate(route_details):
            values = (
                f"{detail['from']} → {detail['to']}",
                f"{detail['distance']:.2f} km",
                f"{detail['travel_time']:.1f} min",
                detail.get("road") or "—",
            )
            for column, value in enumerate(values):
                self.route_table.setItem(row, column, QTableWidgetItem(value))
        self.route_table.setVisible(bool(route_details))
        self.message_label.setText(getattr(result, "message", "") or "Completed.")
        self._refresh_style(self.status_label)

    def set_compact(self, compact):
        for card in self.metric_cards:
            self.metrics_layout.removeWidget(card)
        if compact:
            positions = [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0)]
            for card, (row, column) in zip(self.metric_cards, positions):
                column_span = 2 if card is self.estimated_time else 1
                self.metrics_layout.addWidget(card, row, column, 1, column_span)
        else:
            for column, card in enumerate(self.metric_cards):
                self.metrics_layout.addWidget(card, 0, column)

    @staticmethod
    def _refresh_style(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)


class RouteComparisonPanel(QGroupBox):
    """Mode selector, canonical route metrics and Vietnamese explanation."""

    comparison_requested = pyqtSignal(str, str)

    METRIC_ROWS = (
        ("Distance", "total_distance", "km", 2),
        ("Estimated time", "total_time", "min", 1),
        ("Congestion penalty", "congestion_penalty", "points", 1),
        ("Total cost", "total_cost", "cost units", 2),
    )

    def __init__(self, algorithms=None, parent=None):
        super().__init__("Route comparison", parent)
        self._algorithms = list(algorithms or [])
        self._primary_algorithm = ""
        self._has_result = False
        self.setObjectName("routeComparison")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(10)

        controls = QGridLayout()
        controls.addWidget(QLabel("Comparison mode"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("fieldInput")
        self.mode_combo.addItem(
            "Different algorithms",
            ComparisonMode.DIFFERENT_ALGORITHMS.value,
        )
        self.mode_combo.addItem(
            "Same algorithm · alternative route",
            ComparisonMode.SAME_ALGORITHM_ALTERNATIVE.value,
        )
        controls.addWidget(self.mode_combo, 0, 1)

        self.algorithm_label = QLabel("Compare with")
        controls.addWidget(self.algorithm_label, 1, 0)
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.setObjectName("fieldInput")
        controls.addWidget(self.algorithm_combo, 1, 1)
        controls.setColumnStretch(1, 1)
        layout.addLayout(controls)

        heading_row = QHBoxLayout()
        self.status_label = QLabel("No comparison yet")
        self.status_label.setObjectName("resultStatus")
        self.context_label = QLabel("Selected route vs alternative route")
        self.context_label.setObjectName("mutedLabel")
        heading_row.addWidget(self.status_label)
        heading_row.addStretch()
        heading_row.addWidget(self.context_label)
        layout.addLayout(heading_row)

        self.selected_route_label = QLabel("Route A: —")
        self.alternative_route_label = QLabel("Route B: —")
        for label in (self.selected_route_label, self.alternative_route_label):
            label.setObjectName("routeText")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(label)

        self.metrics_table = QTableWidget(len(self.METRIC_ROWS), 5)
        self.metrics_table.setObjectName("comparisonTable")
        self.metrics_table.setHorizontalHeaderLabels(
            ["Metric", "Selected", "Alternative", "Difference", "Better"]
        )
        self.metrics_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.metrics_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.Stretch
        )
        self.metrics_table.verticalHeader().hide()
        self.metrics_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.metrics_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.metrics_table.setAlternatingRowColors(True)
        self.metrics_table.setMaximumHeight(170)
        layout.addWidget(self.metrics_table)

        explanation_title = QLabel("Giải thích")
        explanation_title.setObjectName("panelTitle")
        layout.addWidget(explanation_title)
        self.explanation_label = QLabel(
            "Chạy một thuật toán để tạo so sánh giữa tuyến được chọn và một tuyến thay thế."
        )
        self.explanation_label.setObjectName("mutedLabel")
        self.explanation_label.setWordWrap(True)
        self.explanation_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.explanation_label)

        self.mode_combo.currentIndexChanged.connect(
            self._on_configuration_changed
        )
        self.algorithm_combo.currentIndexChanged.connect(
            self._on_configuration_changed
        )
        self.reset()

    @staticmethod
    def _path_text(path):
        return " → ".join(str(node_id) for node_id in (path or [])) or "—"

    def _winner_text(self, winner):
        first_label, second_label = self._route_labels()
        return {
            "selected": first_label,
            "alternative": second_label,
            "tie": "Tie",
        }.get(winner, "—")

    def current_mode(self):
        return ComparisonMode.coerce(self.mode_combo.currentData())

    def comparison_algorithm(self):
        if self.current_mode() is ComparisonMode.SAME_ALGORITHM_ALTERNATIVE:
            return self._primary_algorithm
        return self.algorithm_combo.currentText()

    def configure(self, primary_algorithm, algorithms=None):
        self._primary_algorithm = str(primary_algorithm or "")
        if algorithms is not None:
            self._algorithms = list(algorithms)

        previous = self.algorithm_combo.currentText()
        self.algorithm_combo.blockSignals(True)
        self.algorithm_combo.clear()
        for algorithm in self._algorithms:
            if algorithm != self._primary_algorithm:
                self.algorithm_combo.addItem(algorithm)
        if previous and previous != self._primary_algorithm:
            index = self.algorithm_combo.findText(previous)
            if index >= 0:
                self.algorithm_combo.setCurrentIndex(index)
        self.algorithm_combo.blockSignals(False)
        self._apply_mode_labels()

    def set_configuration(self, mode, comparison_algorithm=""):
        mode = ComparisonMode.coerce(mode)
        self.mode_combo.blockSignals(True)
        mode_index = self.mode_combo.findData(mode.value)
        if mode_index >= 0:
            self.mode_combo.setCurrentIndex(mode_index)
        self.mode_combo.blockSignals(False)

        if comparison_algorithm:
            self.algorithm_combo.blockSignals(True)
            index = self.algorithm_combo.findText(comparison_algorithm)
            if index >= 0:
                self.algorithm_combo.setCurrentIndex(index)
            self.algorithm_combo.blockSignals(False)
        self._apply_mode_labels()

    def _route_labels(self):
        if self.current_mode() is ComparisonMode.DIFFERENT_ALGORITHMS:
            return "Route A", "Route B"
        return "Selected", "Alternative"

    def _apply_mode_labels(self):
        different = self.current_mode() is ComparisonMode.DIFFERENT_ALGORITHMS
        self.algorithm_label.setEnabled(different)
        self.algorithm_combo.setEnabled(different and self.mode_combo.isEnabled())
        first_label, second_label = self._route_labels()
        self.metrics_table.setHorizontalHeaderLabels(
            ["Metric", first_label, second_label, "Difference", "Better"]
        )

    def _on_configuration_changed(self):
        self._apply_mode_labels()
        if self._has_result:
            self.comparison_requested.emit(
                self.current_mode().value,
                self.comparison_algorithm(),
            )

    def reset(self, context="Choose a comparison mode"):
        self._has_result = False
        self.status_label.setText("No comparison yet")
        self.status_label.setProperty("resultState", "idle")
        self.context_label.setText(context)
        first_label, second_label = self._route_labels()
        self.selected_route_label.setText(f"{first_label}: —")
        self.alternative_route_label.setText(f"{second_label}: —")
        for row, (label, _attribute, _unit, _decimals) in enumerate(
            self.METRIC_ROWS
        ):
            for column, value in enumerate((label, "—", "—", "—", "—")):
                self.metrics_table.setItem(row, column, QTableWidgetItem(value))
        self.explanation_label.setText(
            "Chạy tìm đường, sau đó chọn so sánh hai thuật toán hoặc một Alternative cùng thuật toán."
        )
        self.mode_combo.setEnabled(True)
        self._apply_mode_labels()
        ResultSummaryPanel._refresh_style(self.status_label)

    def set_running(
        self,
        algorithm,
        start,
        goal,
        mode=None,
        comparison_algorithm="",
    ):
        self.configure(algorithm)
        if mode is not None:
            self.set_configuration(mode, comparison_algorithm)
        self.reset(f"{algorithm} · {start} → {goal}")
        self.status_label.setText("Computing comparison")
        self.status_label.setProperty("resultState", "running")
        self.explanation_label.setText(
            "Đang chạy route thứ hai và tính metric bằng cùng một hàm chuẩn hóa."
        )
        self.mode_combo.setEnabled(False)
        self.algorithm_combo.setEnabled(False)
        ResultSummaryPanel._refresh_style(self.status_label)

    def set_recomputing(self):
        self.status_label.setText("Recomputing comparison")
        self.status_label.setProperty("resultState", "running")
        self.mode_combo.setEnabled(False)
        self.algorithm_combo.setEnabled(False)
        ResultSummaryPanel._refresh_style(self.status_label)

    def set_error(self, message):
        self._has_result = True
        self.status_label.setText("Comparison failed")
        self.status_label.setProperty("resultState", "error")
        self.explanation_label.setText(str(message or "Không thể tạo so sánh."))
        self.mode_combo.setEnabled(True)
        self._apply_mode_labels()
        ResultSummaryPanel._refresh_style(self.status_label)

    def set_comparison(self, comparison):
        if comparison is None:
            self.reset()
            self.status_label.setText("Comparison unavailable")
            self.status_label.setProperty("resultState", "error")
            self.explanation_label.setText(
                "Không có dữ liệu so sánh cho lần chạy này."
            )
            ResultSummaryPanel._refresh_style(self.status_label)
            return

        self._has_result = True
        mode = ComparisonMode.coerce(comparison.mode)
        self.configure(comparison.algorithm)
        self.set_configuration(mode, comparison.comparison_algorithm)
        self.mode_combo.setEnabled(True)
        self._apply_mode_labels()

        selected = comparison.selected
        alternative = comparison.alternative
        first_label, second_label = self._route_labels()
        if mode is ComparisonMode.DIFFERENT_ALGORITHMS:
            context = (
                f"{comparison.algorithm} vs {comparison.comparison_algorithm}"
            )
        else:
            context = f"{comparison.algorithm} · same algorithm"
        self.context_label.setText(context)
        self.selected_route_label.setText(
            f"{first_label} ({comparison.algorithm}): "
            + self._path_text(selected.path)
        )
        self.alternative_route_label.setText(
            f"{second_label} ({comparison.comparison_algorithm}): "
            + (self._path_text(alternative.path) if alternative else "Not found")
        )
        self.status_label.setText(
            "Routes compared"
            if alternative is not None and alternative.valid
            else "Second route not found"
        )
        self.status_label.setProperty(
            "resultState",
            "success"
            if selected.valid and alternative is not None and alternative.valid
            else "error",
        )

        for row, (label, attribute, unit, decimals) in enumerate(self.METRIC_ROWS):
            selected_value = float(getattr(selected, attribute, 0.0))
            alternative_value = (
                float(getattr(alternative, attribute, 0.0))
                if alternative is not None
                else None
            )
            difference = comparison.differences.get(attribute)
            if attribute == "total_distance":
                difference = comparison.differences.get("distance", difference)
            elif attribute == "total_time":
                difference = comparison.differences.get("time", difference)
            winner_key = {
                "total_distance": "distance",
                "total_time": "time",
            }.get(attribute, attribute)
            values = (
                label,
                f"{selected_value:.{decimals}f} {unit}",
                (
                    f"{alternative_value:.{decimals}f} {unit}"
                    if alternative_value is not None
                    else "—"
                ),
                (
                    f"{float(difference):+.{decimals}f} {unit}"
                    if difference is not None
                    else "—"
                ),
                self._winner_text(comparison.winners.get(winner_key)),
            )
            for column, value in enumerate(values):
                self.metrics_table.setItem(row, column, QTableWidgetItem(value))

        explanation = getattr(comparison, "explanation", None)
        self.explanation_label.setText(
            getattr(explanation, "text", "")
            or "Không có nội dung giải thích cho lần chạy này."
        )
        ResultSummaryPanel._refresh_style(self.status_label)


# Compatibility alias for older imports while keeping one canonical component.
DeliveryPanel = ResultSummaryPanel
