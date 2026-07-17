# src/gui/map_widget.py

import json
import os
from pathlib import Path

from PyQt5.QtCore import QTimer, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView


class MapWidget(QWebEngineView):
    """
    QWebEngineView wrapper that renders a Leaflet map and exposes Python APIs
    for drawing a Graph and animating search steps.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._page_loaded = False
        self._pending_graph_data = None
        self._steps = []
        self._step_index = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.apply_next_step)

        self.loadFinished.connect(self._on_load_finished)

        html_path = Path(__file__).resolve().parent / "assets" / "map.html"
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                self.setHtml(f.read(), QUrl.fromLocalFile(os.fspath(html_path.parent) + "/"))
        except Exception as e:
            print(f"[MapWidget ERROR] Failed to read map.html: {e}")

    def _on_load_finished(self, ok):
        self._page_loaded = ok

        if not ok:
            print("[MapWidget ERROR] Failed to load map.html")
            return

        if self._pending_graph_data is not None:
            self._run_js_function("initMap", self._pending_graph_data)
            self._pending_graph_data = None

    def _run_js_function(self, function_name, payload=None):
        if payload is None:
            script = f"{function_name}();"
        else:
            script = f"{function_name}({json.dumps(payload, ensure_ascii=False)});"

        self.page().runJavaScript(script)

    def _serialize_graph(self, graph):
        nodes = []
        for node in graph.nodes.values():
            nodes.append({
                "id": node.id,
                "name": node.name,
                "lat": node.lat,
                "lon": node.lon,
                "type": getattr(node, "type", "intersection"),
            })

        edges = []
        for outgoing_edges in graph.adjacency_list.values():
            for edge in outgoing_edges:
                edges.append({
                    "from": edge.from_node,
                    "to": edge.to_node,
                    "distance": edge.distance,
                    "travel_time": edge.travel_time,
                    "road_type": edge.road_type,
                    "is_one_way": edge.is_one_way,
                    "congestion": edge.congestion,
                    "risk": edge.risk,
                    "note": edge.note,
                })

        return {
            "nodes": nodes,
            "edges": edges,
        }

    def draw_graph(self, graph):
        """Render a Graph object on the Leaflet map."""
        graph_data = self._serialize_graph(graph)

        if self._page_loaded:
            self._run_js_function("initMap", graph_data)
        else:
            self._pending_graph_data = graph_data

    def draw_map_step_by_step(self, steps, interval_ms=500):
        """
        Animate a list of search steps by sending one step to JavaScript per timer tick.
        """
        self.stop_animation()

        self._steps = list(steps or [])
        self._step_index = 0

        if not self._steps:
            return

        self._timer.setInterval(interval_ms)
        self._timer.start()

    def apply_next_step(self):
        """Apply the next queued search step to the map."""
        if self._step_index >= len(self._steps):
            self.stop_animation()
            return

        step = self._steps[self._step_index]
        self._step_index += 1

        if self._page_loaded:
            self._run_js_function("applyStep", step)

        if step.get("type") == "finish":
            self.stop_animation()

    def stop_animation(self):
        """Stop the active animation timer if it is running."""
        if self._timer.isActive():
            self._timer.stop()

    def reset(self):
        """Reset node/edge styles and stop any running animation."""
        self.stop_animation()
        self._step_index = 0

        if self._page_loaded:
            self._run_js_function("resetMap")
