from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
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


# Compatibility alias for older imports while keeping one canonical component.
DeliveryPanel = ResultSummaryPanel
