"""Route location editor used by the Route Setup section."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.models.models import RouteRequest


class RouteSetupWidget(QWidget):
    """Owns all editable Start/Goal state and its Route Setup controls."""

    MAX_GOALS = 100

    selection_changed = pyqtSignal(object)
    validation_error = pyqtSignal(str)
    route_event = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._graph = None
        self._node_ids = []
        self._controls_enabled = True
        self._preview_goal = None
        self._build_ui()
        self._connect_signals()
        self._update_controls()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(self._field_label("Start location"))
        self.start_combo = QComboBox()
        self.start_combo.setObjectName("fieldInput")
        layout.addWidget(self.start_combo)

        layout.addWidget(self._field_label("Add goal"))
        add_layout = QHBoxLayout()
        add_layout.setContentsMargins(0, 0, 0, 0)
        self.add_goal_combo = QComboBox()
        self.add_goal_combo.setObjectName("fieldInput")
        self.add_goal_button = QPushButton("Add")
        self.add_goal_button.setObjectName("addGoalButton")
        add_layout.addWidget(self.add_goal_combo, 1)
        add_layout.addWidget(self.add_goal_button)
        layout.addLayout(add_layout)

        layout.addWidget(self._field_label("Delivery goals"))
        self.goal_list = QListWidget()
        self.goal_list.setObjectName("goalList")
        self.goal_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.goal_list.setDefaultDropAction(Qt.MoveAction)
        self.goal_list.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.goal_list)
        self.remove_goal_button = QPushButton("Remove selected goal")
        self.remove_goal_button.setObjectName("removeGoalButton")
        layout.addWidget(self.remove_goal_button)

        self.return_to_start_checkbox = QCheckBox("Quay về điểm bắt đầu")
        self.return_to_start_checkbox.setObjectName("returnToStartCheck")
        self.return_to_start_checkbox.setChecked(False)
        layout.addWidget(self.return_to_start_checkbox)

        self.respect_goal_order_checkbox = QCheckBox("Đi theo thứ tự danh sách")
        self.respect_goal_order_checkbox.setObjectName("respectGoalOrderCheck")
        self.respect_goal_order_checkbox.setChecked(False)
        layout.addWidget(self.respect_goal_order_checkbox)

    @staticmethod
    def _field_label(text):
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _connect_signals(self):
        self.start_combo.currentIndexChanged.connect(self._on_start_changed)
        self.add_goal_combo.currentIndexChanged.connect(self._on_preview_changed)
        self.add_goal_button.clicked.connect(self._on_add_goal)
        self.remove_goal_button.clicked.connect(self._on_remove_goal)
        self.goal_list.model().rowsMoved.connect(self._on_goal_order_changed)
        self.goal_list.currentItemChanged.connect(lambda *_: self._update_controls())
        self.respect_goal_order_checkbox.toggled.connect(self._on_order_toggled)
        self.return_to_start_checkbox.toggled.connect(self._on_return_toggled)

    @staticmethod
    def _goal_text(node_id, graph):
        node = graph.get_node(node_id) if graph is not None else None
        return f"{node_id} · {node.name}" if node is not None else str(node_id)

    def _goal_ids(self):
        return [
            self.goal_list.item(index).data(Qt.UserRole)
            for index in range(self.goal_list.count())
        ]

    def _append_goal(self, node_id):
        item = QListWidgetItem(self._goal_text(node_id, self._graph))
        item.setData(Qt.UserRole, node_id)
        self.goal_list.addItem(item)

    def _valid_alternative(self):
        start = self.start_combo.currentData()
        return next((node_id for node_id in reversed(self._node_ids) if node_id != start), None)

    def _update_controls(self):
        goals = self._goal_ids()
        can_edit = self._controls_enabled and bool(self._node_ids)
        is_multi = len(goals) >= 2
        if not is_multi and self.return_to_start_checkbox.isChecked():
            self.return_to_start_checkbox.blockSignals(True)
            self.return_to_start_checkbox.setChecked(False)
            self.return_to_start_checkbox.blockSignals(False)
        self.start_combo.setEnabled(can_edit)
        self.add_goal_combo.setEnabled(can_edit)
        self.goal_list.setEnabled(can_edit)
        self.add_goal_button.setEnabled(can_edit and len(goals) < self.MAX_GOALS)
        self.remove_goal_button.setEnabled(
            can_edit and len(goals) >= 2 and self.goal_list.currentItem() is not None
        )
        self.return_to_start_checkbox.setEnabled(can_edit and is_multi)
        self.respect_goal_order_checkbox.setEnabled(can_edit and is_multi)

    def _emit_selection_changed(self):
        self._update_controls()
        self.selection_changed.emit(self.route_request())

    def set_graph(self, graph, node_ids):
        """Load node choices and establish the Start + one Goal default."""
        self._graph = graph
        self._node_ids = list(node_ids or [])
        model = QStandardItemModel(self)
        for node_id in self._node_ids:
            node = graph.get_node(node_id) if graph is not None else None
            item = QStandardItem(
                f"{node_id} · {node.name}" if node is not None else str(node_id)
            )
            item.setData(node_id, Qt.UserRole)
            model.appendRow(item)

        for combo in (self.start_combo, self.add_goal_combo):
            combo.blockSignals(True)
            combo.setModel(model)
            combo.setCurrentIndex(
                (0 if combo is self.start_combo else len(self._node_ids) - 1)
                if self._node_ids
                else -1
            )
            combo.blockSignals(False)
        self.goal_list.clear()
        self.respect_goal_order_checkbox.blockSignals(True)
        self.respect_goal_order_checkbox.setChecked(False)
        self.respect_goal_order_checkbox.blockSignals(False)
        self.return_to_start_checkbox.blockSignals(True)
        self.return_to_start_checkbox.setChecked(False)
        self.return_to_start_checkbox.blockSignals(False)
        default_goal = self._valid_alternative()
        if default_goal is not None:
            self._append_goal(default_goal)
        self._preview_goal = None
        self._update_controls()
        if self._node_ids and default_goal is None:
            self.validation_error.emit("Dataset cần ít nhất hai node khác nhau.")
        self._emit_selection_changed()

    def route_request(self):
        return RouteRequest(
            start_node=self.start_combo.currentData() or "",
            delivery_nodes=tuple(self._goal_ids()),
            respect_goal_order=self.respect_goal_order_checkbox.isChecked(),
            return_to_start=self.return_to_start_checkbox.isChecked(),
        )

    def preview_goal_id(self):
        return self._preview_goal

    def set_controls_enabled(self, enabled):
        self._controls_enabled = bool(enabled)
        self._update_controls()

    def _on_start_changed(self):
        start = self.start_combo.currentData()
        removed_start = False
        for index in range(self.goal_list.count() - 1, -1, -1):
            if self.goal_list.item(index).data(Qt.UserRole) == start:
                self.goal_list.takeItem(index)
                removed_start = True
        if not self._goal_ids():
            fallback = self._valid_alternative()
            if fallback is not None:
                self._append_goal(fallback)
            else:
                self.validation_error.emit("Dataset cần ít nhất hai node khác nhau.")
        self._preview_goal = None
        if start:
            suffix = "; previous goal removed" if removed_start else ""
            self.route_event.emit(f"Start location: {start}{suffix}")
        self._emit_selection_changed()

    def _on_preview_changed(self):
        node_id = self.add_goal_combo.currentData()
        self._preview_goal = (
            node_id
            if node_id
            and node_id != self.start_combo.currentData()
            and node_id not in self._goal_ids()
            else None
        )
        self._emit_selection_changed()

    def _on_add_goal(self):
        node_id = self.add_goal_combo.currentData()
        goals = self._goal_ids()
        if len(goals) >= self.MAX_GOALS:
            self.validation_error.emit(f"Có thể thêm tối đa {self.MAX_GOALS} Goal.")
            return
        if not node_id or node_id == self.start_combo.currentData():
            self.validation_error.emit("Goal không được trùng Start.")
            return
        if node_id in goals:
            self.validation_error.emit("Goal này đã có trong danh sách.")
            return
        self._append_goal(node_id)
        self.goal_list.setCurrentRow(self.goal_list.count() - 1)
        self._preview_goal = None
        self.route_event.emit(f"Added delivery goal: {node_id}")
        self._emit_selection_changed()

    def _on_remove_goal(self):
        if len(self._goal_ids()) < 2:
            self.validation_error.emit("Route Setup phải luôn có ít nhất một Goal.")
            return
        item = self.goal_list.currentItem()
        if item is None:
            return
        node_id = item.data(Qt.UserRole)
        self.goal_list.takeItem(self.goal_list.row(item))
        self.route_event.emit(f"Removed delivery goal: {node_id}")
        self._emit_selection_changed()

    def _on_goal_order_changed(self, *_):
        self.route_event.emit("Delivery goal order updated")
        self._emit_selection_changed()

    def _on_order_toggled(self, _checked):
        self._emit_selection_changed()

    def _on_return_toggled(self, _checked):
        self._emit_selection_changed()

    def set_start_node(self, node_id):
        """Deprecated: select a Start through the exposed Route Setup UI."""
        index = self.start_combo.findData(node_id)
        if index >= 0:
            self.start_combo.setCurrentIndex(index)

    def set_goal_node(self, node_id):
        """Deprecated: configure delivery goals through the Route Setup UI."""
        if node_id == self.start_combo.currentData():
            return
        self.goal_list.clear()
        if node_id in self._node_ids:
            self._append_goal(node_id)
        self._preview_goal = None
        self._emit_selection_changed()
