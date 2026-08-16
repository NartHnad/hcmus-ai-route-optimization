from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class StateList(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("stateList")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        self.title = title
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("stateListTitle")
        self.details_button = QPushButton("View all")
        self.details_button.setObjectName("stateDetailsButton")
        self.details_button.setCheckable(True)
        self.details_button.setAccessibleName(f"Show all {title} nodes")
        self.details_button.hide()
        self.details_button.toggled.connect(self._toggle_details)
        header.addWidget(title_label)
        header.addStretch()
        header.addWidget(self.details_button)
        self.value_label = QLabel("—")
        self.value_label.setObjectName("stateListValue")
        self.value_label.setWordWrap(True)
        self.value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.details_view = QTextEdit()
        self.details_view.setObjectName("stateDetails")
        self.details_view.setReadOnly(True)
        self.details_view.setMaximumHeight(180)
        self.details_view.hide()
        self._values = []
        self._details_dirty = False
        self._details_timer = QTimer(self)
        self._details_timer.setSingleShot(True)
        self._details_timer.setInterval(120)
        self._details_timer.timeout.connect(self._refresh_details)
        layout.addLayout(header)
        layout.addWidget(self.value_label)
        layout.addWidget(self.details_view)

    def set_items(self, items):
        # Keep the current state by reference. Creating and laying out a full
        # QTextDocument for thousands of nodes on every playback tick was one
        # of the main sources of GUI stalls on large datasets.
        values = items or []
        self._values = values
        if not values:
            text = "—"
        elif len(values) <= 8:
            text = "  ·  ".join(map(str, values))
        else:
            text = "  ·  ".join(map(str, values[:8])) + f"  ·  +{len(values) - 8}"
        self.value_label.setText(text)
        self._details_dirty = True
        if self.details_view.isVisible():
            self._details_timer.start()
        has_details = len(values) > 8
        self.details_button.setVisible(has_details)
        if not has_details and self.details_button.isChecked():
            self.details_button.setChecked(False)
        self.details_button.setText(
            "Hide" if self.details_button.isChecked() else f"View all ({len(values)})"
        )
        self.value_label.setToolTip(
            f"{len(values)} node(s). Use View all for the complete list."
            if has_details
            else " → ".join(map(str, values))
        )

    def _toggle_details(self, checked):
        self.details_view.setVisible(checked)
        count = len(getattr(self, "_values", []))
        self.details_button.setText("Hide" if checked else f"View all ({count})")
        if checked:
            self._refresh_details()
        else:
            self._details_timer.stop()

    def _refresh_details(self):
        if not self.details_view.isVisible() or not self._details_dirty:
            return
        self.details_view.setPlainText("\n".join(map(str, self._values)))
        self._details_dirty = False


class AlgorithmStatePanel(QFrame):
    collapse_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("algorithmStatePanel")
        self.setMinimumWidth(210)
        self.setMaximumWidth(680)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Algorithm state")
        title.setObjectName("panelTitle")
        self.collapse_button = QPushButton("Hide")
        self.collapse_button.setObjectName("tertiaryButton")
        self.collapse_button.setToolTip("Collapse algorithm state")
        self.collapse_button.clicked.connect(self.collapse_requested)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.collapse_button)
        outer.addLayout(header)

        self.algorithm_label = QLabel("Select an algorithm")
        self.algorithm_label.setObjectName("mutedLabel")
        outer.addWidget(self.algorithm_label)

        current_card = QFrame()
        current_card.setObjectName("currentNodeCard")
        current_card.setMinimumHeight(72)
        current_layout = QGridLayout(current_card)
        current_layout.setContentsMargins(12, 10, 12, 10)
        current_layout.addWidget(QLabel("CURRENT NODE"), 0, 0)
        self.current_label = QLabel("—")
        self.current_label.setObjectName("currentNodeValue")
        self.step_label = QLabel("Step 0 / 0")
        self.step_label.setObjectName("mutedLabel")
        current_layout.addWidget(self.current_label, 1, 0)
        current_layout.addWidget(self.step_label, 1, 1, alignment=Qt.AlignRight)
        outer.addWidget(current_card)

        metric_frame = QFrame()
        metric_frame.setObjectName("metricStrip")
        metric_frame.setMinimumHeight(58)

        metric_layout = QGridLayout(metric_frame)
        metric_layout.setContentsMargins(8, 7, 8, 7)
        metric_layout.setHorizontalSpacing(8)
        self.metric_values = {}
        self.metric_titles = {}

        for column, key in enumerate(("g", "h", "f")):
            label = QLabel(key.upper())
            label.setObjectName("metricTitle")
            value = QLabel("—")
            value.setObjectName("stateMetricValue")
            metric_layout.addWidget(label, 0, column, alignment=Qt.AlignCenter)
            metric_layout.addWidget(value, 1, column, alignment=Qt.AlignCenter)
            self.metric_titles[key] = label
            self.metric_values[key] = value
        outer.addWidget(metric_frame)

        scroll = QScrollArea()
        scroll.setObjectName("stateScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        scroll_content = QWidget()
        state_layout = QVBoxLayout(scroll_content)
        state_layout.setContentsMargins(0, 0, 0, 0)
        state_layout.setSpacing(8)
        self.frontier = StateList("Frontier")
        self.explored = StateList("Explored")
        self.visited = StateList("Visited order")
        state_layout.addWidget(self.frontier)
        state_layout.addWidget(self.explored)
        state_layout.addWidget(self.visited)
        state_layout.addStretch()
        scroll.setWidget(scroll_content)
        outer.addWidget(scroll, 1)

        self.extra_metrics = QLabel("")
        self.extra_metrics.setObjectName("mutedLabel")
        self.extra_metrics.setWordWrap(True)
        outer.addWidget(self.extra_metrics)

        self._frontier = []
        self._frontier_priorities = {}
        self._explored = []
        self._explored_set = set()
        self._visited = []
        self._current = None

    def reset(self):
        self._reset_state()
        self.current_label.setText("—")
        self.step_label.setText("Step 0 / 0")
        self.frontier.set_items([])
        self.explored.set_items([])
        self.visited.set_items([])
        for value in self.metric_values.values():
            value.setText("—")
        self.extra_metrics.clear()

    def set_algorithm(self, algorithm):
        self.algorithm_label.setText(algorithm or "Select an algorithm")

    def update_step(self, step):
        if step.get("type") == "reset":
            total = step.get("_total", 0)
            self.reset()
            self.step_label.setText(f"Step 0 / {total}")
            return

        history = step.get("_history")
        batch = step.get("_batch")
        if history is not None:
            self._reset_state()
            for item in history:
                self._apply_delta(item)
        elif batch:
            for item in batch:
                self._apply_delta(item)
        else:
            self._apply_delta(step)

        self.current_label.setText(self._current or "—")
        self.step_label.setText(
            f"Step {step.get('_index', 0)} / {step.get('_total', 0)}"
        )
        self.frontier.set_items(self._frontier)
        self.explored.set_items(self._explored)
        self.visited.set_items(self._visited)

        metric_step = self._preferred_metrics_step(step)
        metrics = dict(metric_step.get("metrics") or {})
        metrics.pop("route_reset", None)
        stage = str(metrics.get("stage") or "")

        if stage.startswith("ga_"):
            # Reuse the compact 3-value strip for GA instead of showing meaningless
            # A* G/H/F placeholders.  Operator events may not have all three values.
            self.metric_titles["g"].setText("GEN")
            self.metric_titles["h"].setText("ROUTE")
            self.metric_titles["f"].setText("GLOBAL")

            generation = metrics.pop("generation", None)
            route_value = None
            for candidate_key in (
                "candidate_cost",
                "generation_best_cost",
                "route_cost",
                "best_cost",
                "parent1_cost",
            ):
                if candidate_key in metrics:
                    route_value = metrics.pop(candidate_key)
                    break
            global_value = metrics.pop("global_best_cost", None)
            if global_value is None and stage == "ga_best":
                global_value = route_value

            ga_values = {"g": generation, "h": route_value, "f": global_value}
            for key, label in self.metric_values.items():
                value = ga_values[key]
                label.setText("—" if value is None else self._format_metric(value))
        elif stage.startswith("sa_"):
            # SA has no graph-search G/H/F values. Show the quantities that drive
            # the annealing decision instead.
            self.metric_titles["g"].setText("ITER")
            self.metric_titles["h"].setText("TEMP")
            self.metric_titles["f"].setText("BEST")

            sa_values = {
                "g": metrics.pop("time_step", None),
                "h": metrics.pop("temperature", None),
                "f": metrics.pop("best_distance", None),
            }
            for key, label in self.metric_values.items():
                value = sa_values[key]
                label.setText("—" if value is None else self._format_metric(value))

            # Route strings and frame identifiers are useful for logs/playback but
            # make this compact panel unreadable. Goal order is already visible in
            # endpoint badges on Map/Graph.
            for hidden_key in (
                "route_frame",
                "route",
                "goal_order",
                "previous_tour",
                "candidate_tour",
                "current_tour",
                "best_tour",
            ):
                metrics.pop(hidden_key, None)
        elif stage.startswith("nn2opt_"):
            # NN + 2-Opt is a route optimizer, so graph-search G/H/F values are
            # not meaningful.  During NN show selection progress/cost; during
            # 2-Opt show before/after costs for the accepted improvement.
            if stage.startswith("nn2opt_2opt"):
                self.metric_titles["g"].setText("ITER")
                self.metric_titles["h"].setText("BEFORE")
                self.metric_titles["f"].setText("AFTER")
                values = {
                    "g": metrics.pop("iteration", None),
                    "h": metrics.pop("previous_cost", None),
                    "f": metrics.pop("optimized_cost", metrics.get("route_cost")),
                }
            else:
                self.metric_titles["g"].setText("STEP")
                self.metric_titles["h"].setText("ROUTE")
                self.metric_titles["f"].setText("NN COST")
                values = {
                    "g": metrics.pop("iteration", None),
                    "h": metrics.pop("route_cost", metrics.pop("partial_cost", None)),
                    "f": metrics.pop("nearest_neighbor_cost", None),
                }

            for key, label in self.metric_values.items():
                value = values[key]
                label.setText("—" if value is None else self._format_metric(value))

            for hidden_key in (
                "route_frame",
                "route",
                "goal_order",
                "remaining_goals",
            ):
                metrics.pop(hidden_key, None)
        else:
            for key, title in (("g", "G"), ("h", "H"), ("f", "F")):
                self.metric_titles[key].setText(title)
                value = metrics.pop(key, None)
                self.metric_values[key].setText(
                    "—" if value is None else self._format_metric(value)
                )

        self.extra_metrics.setText(
            "  ·  ".join(
                f"{key.replace('_', ' ').title()}: {self._format_metric(value)}"
                for key, value in metrics.items()
            )
        )

    def _reset_state(self):
        self._frontier = []
        self._frontier_priorities = {}
        self._explored = []
        self._explored_set = set()
        self._visited = []
        self._current = None

    @staticmethod
    def _stage(step):
        metrics = step.get("metrics") or {}
        return str(metrics.get("stage") or "") if isinstance(metrics, dict) else ""

    @classmethod
    def _is_optimizer_route_step(cls, step):
        stage = cls._stage(step)
        return (
            stage.startswith("ga_generation_route")
            or stage.startswith("ga_final_route")
            or stage.startswith("sa_initial_route")
            or stage.startswith("sa_iteration_route")
            or stage.startswith("sa_final_route")
            or stage.startswith("nn2opt_nn_route")
            or stage.startswith("nn2opt_2opt_route")
            or stage.startswith("nn2opt_preserved_route")
            or stage.startswith("nn2opt_final_route")
        )

    @classmethod
    def _is_optimizer_logical_update(cls, step):
        stage = cls._stage(step)
        return (
            step.get("type") == "update"
            and (
                stage.startswith("ga_")
                or stage.startswith("sa_")
                or stage.startswith("nn2opt_")
            )
            and not step.get("from")
            and not step.get("to")
        )

    @classmethod
    def _preferred_metrics_step(cls, step):
        """Use the route-start marker metrics for an atomic optimizer batch."""
        metrics = step.get("metrics") or {}
        if not isinstance(metrics, dict):
            return step

        route_frame = metrics.get("route_frame")
        if route_frame is None:
            return step

        events = step.get("_batch") or step.get("_history") or []
        for item in reversed(events):
            item_metrics = item.get("metrics") or {}
            if not isinstance(item_metrics, dict):
                continue
            if item_metrics.get("route_frame") == route_frame and item_metrics.get(
                "route_reset"
            ):
                return item
        return step

    def _apply_delta(self, step):
        """Apply one visualization event without changing search semantics."""
        step_type = step.get("type")
        node = step.get("node")
        metrics = step.get("metrics") or {}

        # Each visualized optimizer route frame replaces the previous tour. Clear
        # state lists so Previous/Next and the panel match Map/Graph View.
        if isinstance(metrics, dict) and metrics.get("route_reset"):
            self._reset_state()

        optimizer_route_step = self._is_optimizer_route_step(step)
        optimizer_logical_update = self._is_optimizer_logical_update(step)

        # Backward compatibility for bounded producers such as the GA and for
        # external/legacy SearchStep instances that still provide snapshots.
        if "frontier" in step:
            self._frontier = list(step.get("frontier") or [])
            self._frontier_priorities.clear()
        if "explored" in step:
            self._explored = list(step.get("explored") or [])
            self._explored_set = set(self._explored)
        if "visited_order" in step:
            self._visited = list(step.get("visited_order") or [])

        uses_snapshot = any(
            key in step for key in ("frontier", "explored", "visited_order")
        )
        if not uses_snapshot:
            if step_type == "discover" and node and not optimizer_route_step:
                self._add_frontier(node, step)
            elif step_type == "update" and node and not optimizer_logical_update:
                self._add_frontier(node, step)
            elif step_type == "expand" and node:
                self._remove_frontier(node)
                if node not in self._explored_set:
                    self._explored_set.add(node)
                    self._explored.append(node)
                    self._visited.append(node)

        if step_type == "expand":
            self._current = node
        elif step_type == "finish":
            self._current = None

    def _add_frontier(self, node, step):
        if node in self._explored_set:
            return
        self._remove_frontier(node)
        position = step.get("frontier_position", "back")

        if position == "front":
            self._frontier.insert(0, node)
        else:
            self._frontier.append(node)

        metrics = step.get("metrics") or {}
        priority = None

        if position == "priority" and "f" in metrics:
            priority = (float(metrics["f"]), float(metrics.get("g", 0.0)), str(node))
        elif position == "priority" and "g" in metrics:
            priority = (float(metrics["g"]), str(node))
        if priority is not None:
            self._frontier_priorities[node] = priority
            self._frontier.sort(
                key=lambda item: self._frontier_priorities.get(
                    item, (float("inf"), str(item))
                )
            )

    def _remove_frontier(self, node):
        self._frontier = [item for item in self._frontier if item != node]
        self._frontier_priorities.pop(node, None)

    @staticmethod
    def _format_metric(value):
        if isinstance(value, float):
            return f"{value:,.2f}"
        return str(value)
