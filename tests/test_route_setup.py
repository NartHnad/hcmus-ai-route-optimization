import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from src.gui.route_setup_widget import RouteSetupWidget
from src.models.models import Graph, Node


def _widget(node_ids):
    app = QApplication.instance() or QApplication([])
    graph = Graph()
    for node_id in node_ids:
        graph.add_node(Node(node_id, node_id, 10.0, 106.0))
    widget = RouteSetupWidget()
    widget.set_graph(graph, node_ids)
    return app, widget


def _goals(widget):
    return list(widget.route_request().delivery_nodes)


def test_route_setup_initializes_one_goal_and_switches_route_mode():
    _app, widget = _widget(["N1", "N2", "N10"])
    try:
        assert _goals(widget) == ["N10"]
        assert widget.route_request().route_mode == "single"
        assert not widget.remove_goal_button.isEnabled()
        assert not widget.route_request().respect_goal_order
        assert not widget.route_request().return_to_start
        assert not widget.return_to_start_checkbox.isEnabled()

        widget.add_goal_combo.setCurrentIndex(1)
        assert widget.preview_goal_id() == "N2"
        widget.add_goal_button.click()

        assert _goals(widget) == ["N10", "N2"]
        assert widget.route_request().route_mode == "multi"
        assert widget.remove_goal_button.isEnabled()
        assert widget.return_to_start_checkbox.isEnabled()
        assert widget.preview_goal_id() is None
    finally:
        widget.close()


def test_route_setup_keeps_one_goal_when_start_conflicts_and_remove_is_locked():
    _app, widget = _widget(["N1", "N2", "N10"])
    try:
        widget.set_start_node("N10")
        assert widget.route_request().start_node == "N10"
        assert _goals(widget) == ["N2"]
        assert not widget.remove_goal_button.isEnabled()
    finally:
        widget.close()


def test_return_to_start_is_reset_when_route_becomes_single():
    _app, widget = _widget(["N1", "N2", "N10"])
    try:
        widget.add_goal_combo.setCurrentIndex(widget.add_goal_combo.findData("N2"))
        widget.add_goal_button.click()
        widget.return_to_start_checkbox.setChecked(True)
        assert widget.route_request().return_to_start

        widget.goal_list.setCurrentRow(1)
        widget.remove_goal_button.click()

        assert widget.route_request().route_mode == "single"
        assert not widget.route_request().return_to_start
        assert not widget.return_to_start_checkbox.isEnabled()
    finally:
        widget.close()


def test_route_setup_reorders_goals_and_emits_preview_selection():
    _app, widget = _widget(["N1", "N2", "N10"])
    try:
        snapshots = []
        widget.selection_changed.connect(snapshots.append)
        widget.add_goal_combo.setCurrentIndex(1)
        assert snapshots[-1].delivery_nodes == ("N10",)
        assert widget.preview_goal_id() == "N2"
        widget.add_goal_button.click()

        first = widget.goal_list.takeItem(0)
        widget.goal_list.insertItem(1, first)
        widget._on_goal_order_changed()
        assert _goals(widget) == ["N2", "N10"]
    finally:
        widget.close()


def test_route_setup_rejects_duplicate_start_and_goal_101():
    node_ids = [f"N{index}" for index in range(102)]
    _app, widget = _widget(node_ids)
    errors = []
    widget.validation_error.connect(errors.append)
    try:
        for node_id in node_ids[1:100]:
            widget.add_goal_combo.setCurrentIndex(widget.add_goal_combo.findData(node_id))
            widget.add_goal_button.click()
        assert len(_goals(widget)) == 100
        assert not widget.add_goal_button.isEnabled()

        widget.add_goal_combo.setCurrentIndex(widget.add_goal_combo.findData("N100"))
        widget._on_add_goal()
        assert len(_goals(widget)) == 100
        assert errors[-1] == "Có thể thêm tối đa 100 Goal."

        widget.add_goal_combo.setCurrentIndex(widget.add_goal_combo.findData("N0"))
        widget._on_add_goal()
        assert widget.route_request().start_node not in _goals(widget)
    finally:
        widget.close()


def test_route_setup_removes_goal_and_disables_controls():
    _app, widget = _widget(["N1", "N2", "N3"])
    try:
        widget.add_goal_combo.setCurrentIndex(1)
        widget.add_goal_button.click()
        assert len(_goals(widget)) == 2
        assert widget.route_request().route_mode == "multi"
        assert widget.remove_goal_button.isEnabled()
        assert widget.respect_goal_order_checkbox.isEnabled()

        widget.goal_list.setCurrentRow(0)
        widget.remove_goal_button.click()

        assert _goals(widget) == ["N2"]
        assert widget.route_request().route_mode == "single"
        assert not widget.remove_goal_button.isEnabled()
        assert not widget.respect_goal_order_checkbox.isEnabled()
    finally:
        widget.close()


def test_route_setup_validation_errors():
    _app, widget = _widget(["N1", "N2", "N3"])
    errors = []
    widget.validation_error.connect(errors.append)
    try:
        widget.add_goal_combo.setCurrentIndex(widget.add_goal_combo.findData("N3"))
        widget._on_add_goal()
        assert errors[-1] == "Goal này đã có trong danh sách."

        widget.goal_list.setCurrentRow(0)
        widget._on_remove_goal()
        assert errors[-1] == "Route Setup phải luôn có ít nhất một Goal."
    finally:
        widget.close()


def test_route_setup_too_few_nodes():
    app = QApplication.instance() or QApplication([])
    graph = Graph()
    graph.add_node(Node("N1", "N1", 10.0, 106.0))
    widget = RouteSetupWidget()
    errors = []
    widget.validation_error.connect(errors.append)
    widget.set_graph(graph, ["N1"])
    try:
        assert errors[-1] == "Dataset cần ít nhất hai node khác nhau."
    finally:
        widget.close()


def test_route_setup_toggle_order_checkbox():
    _app, widget = _widget(["N1", "N2", "N3"])
    try:
        widget.add_goal_combo.setCurrentIndex(1)
        widget.add_goal_button.click()
        assert len(_goals(widget)) == 2
        assert not widget.route_request().respect_goal_order
        
        widget.respect_goal_order_checkbox.setChecked(True)
        assert widget.route_request().respect_goal_order
    finally:
        widget.close()


def test_route_setup_deprecated_set_goal_node():
    _app, widget = _widget(["N1", "N2", "N3"])
    try:
        assert _goals(widget) == ["N3"]
        widget.set_goal_node("N2")
        assert _goals(widget) == ["N2"]
        widget.set_goal_node("N1")
        assert _goals(widget) == ["N2"]
    finally:
        widget.close()
