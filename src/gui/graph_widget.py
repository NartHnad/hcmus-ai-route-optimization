import json
import os
from pathlib import Path

from PyQt5.QtCore import QTimer, QUrl, pyqtSignal
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView

from src.gui.edge_editor_bridge import EdgeEditorBridge
from src.gui.route_selection import normalize_route_selection
from src.models.graph_updater import serialize_visual_edges

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
        self._selection_payload = normalize_route_selection(None, [])
        self._theme = "light"
        self._render_enabled = False
        self._edge_editing_enabled = False

        self._web_channel = QWebChannel(self.page())
        self._edge_bridge = EdgeEditorBridge(self)
        self._web_channel.registerObject("edgeBridge", self._edge_bridge)
        self.page().setWebChannel(self._web_channel)

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
        self.set_edge_editing_enabled(self._edge_editing_enabled)
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
        return {"nodes": nodes, "edges": serialize_visual_edges(graph)}

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

    def set_edge_update_handler(self, handler):
        self._edge_bridge.set_update_handler(handler)

    def set_edge_editing_enabled(self, enabled):
        self._edge_editing_enabled = bool(enabled)
        self._run_js_function(
            "setEdgeEditingEnabled", {"enabled": self._edge_editing_enabled}
        )

    def update_edge_direction(self, edge_payload):
        self._run_js_function("updateEdgeDirection", edge_payload)

    def set_start_node(self, node_id):
        """Deprecated: use :meth:`set_route_locations` instead."""
        self._selection_payload = normalize_route_selection(
            node_id, self._selection_payload["goals"],
            self._selection_payload["display_order"],
            self._selection_payload["preview_goal"],
        )
        self._update_selection()

    def set_goal_node(self, node_id):
        """Deprecated: use :meth:`set_route_locations` instead."""
        self._selection_payload = normalize_route_selection(
            self._selection_payload["start"], [node_id] if node_id else []
        )
        self._update_selection()

    def set_route_locations(
        self,
        start_id,
        goal_ids,
        display_order=None,
        preview_goal=None,
    ):
        self._selection_payload = normalize_route_selection(
            start_id, goal_ids, display_order, preview_goal
        )
        self._update_selection()

    def _update_selection(self):
        self._run_js_function("updateSelection", self._selection_payload)

    def set_theme(self, theme_name):
        self._theme = theme_name
        self._run_js_function("setTheme", {"theme": theme_name})
