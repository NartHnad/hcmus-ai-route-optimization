import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget

import src.gui.main_window as main_window_module
from src.models.models import Graph, Node


class FakeMapWidget(QWidget):
    animation_finished = pyqtSignal()
    step_changed = pyqtSignal(dict)
    playback_state_changed = pyqtSignal(str)
    graph_ready = pyqtSignal()
    graph_render_failed = pyqtSignal(str)
    step_count = 0
    step_index = 0

    def set_theme(self, *_args):
        pass

    def set_visual_updates_enabled(self, *_args):
        pass

    def set_route_locations(self, *args):
        self.route_locations = args
        self.route_location_calls = getattr(self, "route_location_calls", [])
        self.route_location_calls.append(args)

    def set_playback_profile(self, *_args, **_kwargs):
        pass


class FakeGraphWidget(QWidget):
    graph_ready = pyqtSignal()
    graph_render_failed = pyqtSignal(str)

    def set_theme(self, *_args):
        pass

    def set_render_enabled(self, *_args):
        pass

    def set_route_locations(self, *args):
        self.route_locations = args
        self.route_location_calls = getattr(self, "route_location_calls", [])
        self.route_location_calls.append(args)


def _build_window(monkeypatch, node_ids):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window_module, "MapWidget", FakeMapWidget)
    monkeypatch.setattr(main_window_module, "GraphWidget", FakeGraphWidget)
    window = main_window_module.MainWindow()
    graph = Graph()
    for node_id in node_ids:
        graph.add_node(Node(node_id, node_id, 10.0, 106.0))
    window.graph = graph
    window._populate_node_combos(node_ids)
    window.on_start_changed(window.start_combo.currentIndex())
    window._set_execution_state("ready")
    return app, window


def test_route_setup_keeps_one_goal_and_switches_algorithm_modes(monkeypatch):
    _app, window = _build_window(monkeypatch, ["N1", "N2", "N10"])
    try:
        assert window.delivery_nodes == ["N10"]
        assert not window.remove_goal_button.isEnabled()
        assert window.route_request()["respect_goal_order"] is False

        window.add_goal_combo.setCurrentIndex(1)
        window.on_add_goal_clicked()

        assert window.delivery_nodes == ["N10", "N2"]
        assert window.algorithm_combo.currentText() == "Mock Multi-location Search"
        assert window.remove_goal_button.isEnabled()
        assert window.map_widget.route_locations == (
            "N1",
            ["N10", "N2"],
            ["N10", "N2"],
            None,
        )

        window.goal_list.setCurrentRow(0)
        window.on_remove_goal_clicked()

        assert window.delivery_nodes == ["N2"]
        assert not window.remove_goal_button.isEnabled()
        algorithms = [
            window.algorithm_combo.itemText(index)
            for index in range(window.algorithm_combo.count())
        ]
        assert "A* Search" in algorithms
    finally:
        window.close()


def test_goal_selector_previews_an_unadded_goal_immediately(monkeypatch):
    _app, window = _build_window(monkeypatch, ["N1", "N2", "N10"])
    try:
        window.add_goal_combo.setCurrentIndex(1)

        assert window.delivery_nodes == ["N10"]
        assert window.map_widget.route_locations == (
            "N1",
            ["N10"],
            ["N10"],
            "N2",
        )
        assert window.graph_widget.route_locations == window.map_widget.route_locations

        window.on_add_goal_clicked()

        assert window.delivery_nodes == ["N10", "N2"]
        assert window.map_widget.route_locations == (
            "N1",
            ["N10", "N2"],
            ["N10", "N2"],
            None,
        )
    finally:
        window.close()


def test_route_markers_resync_after_renderer_ready_and_location_changes(monkeypatch):
    _app, window = _build_window(monkeypatch, ["N1", "N2", "N10"])
    try:
        default_selection = ("N1", ["N10"], ["N10"], None)
        assert window.map_widget.route_locations == default_selection
        assert window.graph_widget.route_locations == default_selection

        map_calls = len(window.map_widget.route_location_calls)
        graph_calls = len(window.graph_widget.route_location_calls)
        window.on_visualization_render_ready("map")

        assert len(window.map_widget.route_location_calls) == map_calls + 1
        assert len(window.graph_widget.route_location_calls) == graph_calls + 1
        assert window.map_widget.route_locations == default_selection
        assert window.graph_widget.route_locations == default_selection

        window.add_goal_combo.setCurrentIndex(1)
        window.on_add_goal_clicked()
        first_goal = window.goal_list.takeItem(0)
        window.goal_list.insertItem(1, first_goal)
        window._sync_delivery_nodes()

        reordered_selection = (
            "N1",
            ["N2", "N10"],
            ["N2", "N10"],
            None,
        )
        assert window.map_widget.route_locations == reordered_selection
        assert window.graph_widget.route_locations == reordered_selection

        window.start_combo.setCurrentIndex(1)

        start_changed_selection = ("N2", ["N10"], ["N10"], None)
        assert window.delivery_nodes == ["N10"]
        assert window.map_widget.route_locations == start_changed_selection
        assert window.graph_widget.route_locations == start_changed_selection
    finally:
        window.close()


def test_route_setup_rejects_duplicate_start_and_goal_101(monkeypatch):
    node_ids = [f"N{index}" for index in range(102)]
    _app, window = _build_window(monkeypatch, node_ids)
    try:
        for node_id in node_ids[1:100]:
            if node_id not in window.delivery_nodes:
                window._append_goal_item(node_id)
        window._sync_delivery_nodes()
        assert len(window.delivery_nodes) == 100
        assert not window.add_goal_button.isEnabled()

        window.add_goal_combo.setCurrentIndex(100)
        window.on_add_goal_clicked()
        assert len(window.delivery_nodes) == 100

        start_id = window.current_start_id()
        window.add_goal_combo.setCurrentIndex(0)
        window.on_add_goal_clicked()
        assert start_id not in window.delivery_nodes
    finally:
        window.close()
