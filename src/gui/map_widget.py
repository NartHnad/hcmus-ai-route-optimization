# src/gui/map_widget.py

import json
import os
from pathlib import Path

from PyQt5.QtCore import QTimer, QUrl, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView

from src.models.models import SearchResult
from src.utils.node_visibility import is_visible_node  # #NhatHuyChanged


class MapWidget(QWebEngineView):
    """
    QWebEngineView wrapper that renders a Leaflet map and exposes Python APIs
    for drawing a Graph and animating a SearchResult.

    Boundary rule: everything on the Python side speaks Graph / SearchResult;
    everything past _run_js_function speaks plain dicts / JSON. This class is
    the only translator between the two.
    """

    animation_finished = pyqtSignal()
    step_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._page_loaded = False
        self._pending_graph_data = None
        self._steps = []
        self._step_index = 0
        self._result = None

        self._is_paused = False

        self._current_start = None
        self._current_goal = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.apply_next_step)

        self.loadFinished.connect(self._on_load_finished)

        html_path = Path(__file__).resolve().parent / "assets" / "map.html"
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                self.setHtml(
                    f.read(), QUrl.fromLocalFile(os.fspath(html_path.parent) + "/")
                )
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
        # #NhatHuyChanged: compute which nodes are allowed to be drawn.
        visible_node_ids = {
            node.id for node in graph.nodes.values() if is_visible_node(node)
        }

        nodes = []
        for node in graph.nodes.values():
            nodes.append(
                {
                    "id": node.id,
                    "name": node.name,
                    "lat": node.lat,
                    "lon": node.lon,
                    "type": getattr(node, "node_type", "intersection"),
                    "name_kind": getattr(node, "name_kind", ""),  # #NhatHuyChanged
                    "visible": node.id in visible_node_ids,  # #NhatHuyChanged
                }
            )

        edges = []
        for outgoing_edges in graph.adjacency_list.values():
            for edge in outgoing_edges:
                # #NhatHuyChanged: hide edges connected to hidden nodes.
                visible = (
                    edge.from_node in visible_node_ids
                    and edge.to_node in visible_node_ids
                )
                edges.append(
                    {
                        "from": edge.from_node,
                        "to": edge.to_node,
                        "distance": edge.distance,
                        "travel_time": edge.travel_time,
                        "road_type": edge.road_type,
                        "is_one_way": edge.is_one_way,
                        "congestion": edge.congestion,
                        "risk": edge.risk,
                        "note": edge.note,
                        "visible": visible,  # #NhatHuyChanged
                    }
                )

        return {
            "nodes": nodes,
            "edges": edges,
            "visible_nodes": len(visible_node_ids),  # #NhatHuyChanged
            "hidden_nodes": len(nodes) - len(visible_node_ids),  # #NhatHuyChanged
        }

    # ========================
    # DRAWING
    # ========================

    def draw_graph(self, graph):
        """Render a Graph object on the Leaflet map."""
        graph_data = self._serialize_graph(graph)

        if self._page_loaded:
            self._run_js_function("initMap", graph_data)
        else:
            self._pending_graph_data = graph_data

    def draw_map_step_by_step(self, result, interval_ms=500):
        """
        Animate a search process. Accepts either a SearchResult object (new contract)
        or a list of step dicts (legacy/mock contract) and replays them on the map.
        """
        self.stop_animation()

        if isinstance(result, SearchResult):
            self._result = result
            self._steps = list(result.steps)
        else:
            self._result = SearchResult(
                path=[],
                steps=list(result or []),
                success=False,
                message="Legacy step-by-step data provided; no final path available.",
            )
            self._steps = self._result.steps

        self._step_index = 0
        self._is_paused = False

        if not self._steps:
            return

        self._timer.setInterval(interval_ms)
        self._timer.start()

    def apply_next_step(self):
        """Apply the next queued search step to the map."""
        if self._step_index >= len(self._steps):
            self.stop_animation()
            self.animation_finished.emit()
            return

        step = self._steps[self._step_index]
        self._step_index += 1

        if hasattr(step, "to_dict"):
            step_dict = step.to_dict()
        else:
            step_dict = dict(step)

        # The final path belongs to the SearchResult, not to any single step —
        # attach it to the 'finish' step so JS can highlight the whole path.
        if step_dict.get("type") == "finish" and self._result is not None:
            step_dict.setdefault("path", list(self._result.path))

        # Send step to JavaScript
        if self._page_loaded:
            self._run_js_function("applyStep", step_dict)

        # Keep Python-side status logging working
        self.step_changed.emit(step_dict)

        if step_dict["type"] == "finish":
            self.stop_animation()
            self.animation_finished.emit()

    def stop_animation(self):
        """Stop the active animation timer if it is running."""
        if self._timer.isActive():
            self._timer.stop()
        self._is_paused = False

    def pause_animation(self):
        """Pause current animation."""
        if self._timer.isActive():
            self._timer.stop()

        self._is_paused = True

    def resume_animation(self):
        if (
            self._is_paused
            and not self._timer.isActive()
            and self._step_index < len(self._steps)
        ):
            self._timer.start()
            self._is_paused = False

    def replay_animation(self):
        if not self._steps:
            return

        self.stop_animation()

        self._step_index = 0

        self._timer.start()

    def next_step(self):
        if self._timer.isActive():
            self._timer.stop()

        self.apply_next_step()

    def reset(self):
        """Reset node/edge styles and stop any running animation."""
        self.stop_animation()

        self._step_index = 0
        self._result = None

        self._steps.clear()

        if self._page_loaded:
            self._run_js_function("resetMap")
            self._update_selection()

    def set_start_node(self, node_id):
        if not self._page_loaded:
            return

        self._current_start = node_id
        self._update_selection()

    def set_goal_node(self, node_id):
        if not self._page_loaded:
            return

        self._current_goal = node_id
        self._update_selection()

    def _update_selection(self):
        self._run_js_function(
            "updateSelection",
            {
                "start": self._current_start,
                "goal": self._current_goal,
            },
        )
