import json
import os
from pathlib import Path

from PyQt5.QtCore import QTimer, QUrl, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView


class GraphWidget(QWebEngineView):
    """Canvas graph renderer that mirrors MapWidget playback events."""

    graph_ready = pyqtSignal()
    graph_render_failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("graphView")
        self.setMinimumSize(220, 220)
        self._page_loaded = False
        self._pending_graph_data = None
        self._graph_generation = 0
        self._current_start = None
        self._current_goal = None
        self._theme = "light"
        self._render_enabled = False

        self.loadFinished.connect(self._on_load_finished)
        html_path = Path(__file__).resolve().parent / "assets" / "graph.html"
        try:
            with open(html_path, "r", encoding="utf-8") as file:
                self.setHtml(
                    file.read(),
                    QUrl.fromLocalFile(os.fspath(html_path.parent) + "/"),
                )
        except OSError as exc:
            self.graph_render_failed.emit(str(exc))

    def _on_load_finished(self, ok):
        self._page_loaded = ok
        if not ok:
            self.graph_render_failed.emit("Failed to load graph.html")
            return
        self.set_theme(self._theme)
        self.set_render_enabled(self._render_enabled)
        if self._pending_graph_data is not None:
            graph_data = self._pending_graph_data
            self._pending_graph_data = None
            self._start_graph_render(graph_data)
        self._update_selection()

    def _run_js_function(self, function_name, payload=None, callback=None):
        if not self._page_loaded:
            if callback is not None:
                QTimer.singleShot(0, lambda: callback(None))
            return False
        script = function_name + "()"
        if payload is not None:
            script = f"{function_name}({json.dumps(payload, ensure_ascii=False)})"
        if callback is None:
            self.page().runJavaScript(script)
        else:
            self.page().runJavaScript(script, callback)
        return True

    @staticmethod
    def _serialize_graph(graph):
        nodes = [
            {
                "id": node.id,
                "name": node.name,
                "lat": node.lat,
                "lon": node.lon,
                "type": getattr(node, "node_type", "intersection"),
            }
            for node in graph.nodes.values()
        ]
        visual_edges = {}
        direction_sets = {}
        for outgoing_edges in graph.adjacency_list.values():
            for edge in outgoing_edges:
                pair = tuple(sorted((edge.from_node, edge.to_node)))
                if pair not in visual_edges:
                    visual_edges[pair] = {
                        "from": edge.from_node,
                        "to": edge.to_node,
                        "distance": edge.distance,
                        "travel_time": edge.travel_time,
                        "cost": edge.calculate_cost(),
                        "road_type": edge.road_type,
                        "note": edge.note,
                        "directions": [],
                    }
                    direction_sets[pair] = set()
                direction = (edge.from_node, edge.to_node)
                if direction not in direction_sets[pair]:
                    direction_sets[pair].add(direction)
                    visual_edges[pair]["directions"].append(list(direction))
        return {"nodes": nodes, "edges": list(visual_edges.values())}

    def draw_graph(self, graph):
        graph_data = self._serialize_graph(graph)
        self._graph_generation += 1
        graph_data["render_token"] = self._graph_generation
        if self._page_loaded:
            self._start_graph_render(graph_data)
        else:
            self._pending_graph_data = graph_data

    def _start_graph_render(self, graph_data):
        token = graph_data["render_token"]

        def rendered(result):
            if token != self._graph_generation:
                return
            if isinstance(result, dict) and result.get("error"):
                self.graph_render_failed.emit(str(result["error"]))
                return
            self._update_selection()
            self.graph_ready.emit()

        self._run_js_function("initGraph", graph_data, rendered)

    def apply_playback_event(self, step):
        if step.get("type") == "reset":
            self.reset_visualization()
            return
        history = step.get("_history")
        if history is not None:
            self._run_js_function("renderSteps", history)
            return
        batch = step.get("_batch")
        if batch:
            self._run_js_function("applySteps", batch)
            return
        self._run_js_function("applyStep", step)

    def reset_visualization(self):
        self._run_js_function("resetVisualization")

    def set_render_enabled(self, enabled):
        self._render_enabled = bool(enabled)
        self._run_js_function("setRenderEnabled", {"enabled": self._render_enabled})

    def set_start_node(self, node_id):
        self._current_start = node_id or None
        self._update_selection()

    def set_goal_node(self, node_id):
        self._current_goal = node_id or None
        self._update_selection()

    def _update_selection(self):
        self._run_js_function(
            "updateSelection",
            {"start": self._current_start, "goal": self._current_goal},
        )

    def set_theme(self, theme_name):
        self._theme = theme_name
        self._run_js_function("setTheme", {"theme": theme_name})
