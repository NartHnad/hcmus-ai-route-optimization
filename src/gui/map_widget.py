import json
import math
import os
import time
from pathlib import Path

from PyQt5.QtCore import QTimer, QUrl, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView

from src.gui.route_selection import normalize_route_selection
from src.models.models import SearchResult


class MapWidget(QWebEngineView):
    """Leaflet renderer and backpressured playback controller for Map View."""

    animation_finished = pyqtSignal()
    step_changed = pyqtSignal(dict)
    playback_state_changed = pyqtSignal(str)
    graph_ready = pyqtSignal()
    graph_render_failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("mapView")
        self.setMinimumSize(220, 220)

        self._page_loaded = False
        self._pending_graph_data = None
        self._graph_generation = 0
        self._steps = []
        self._step_index = 0
        self._result = None
        self._interval_ms = 100
        self._target_duration_ms = 15000
        self._auto_batch_size = 1
        self._dispatch_started_at = None
        self._playback_deadline = None
        self._paused_at = None
        self._is_paused = False
        self._manual_mode = False
        self._finished_emitted = False
        self._selection_payload = normalize_route_selection(None, [])
        self._theme = "light"
        self._js_step_in_flight = False
        self._playback_generation = 0
        self._pending_navigation = None
        self._graph_node_count = 0
        self._visual_updates_enabled = True

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timer_timeout)
        self.loadFinished.connect(self._on_load_finished)

        html_path = Path(__file__).resolve().parent / "assets" / "map.html"
        try:
            with open(html_path, "r", encoding="utf-8") as file:
                self.setHtml(
                    file.read(),
                    QUrl.fromLocalFile(os.fspath(html_path.parent) + "/"),
                )
        except OSError as exc:
            print(f"[MapWidget ERROR] Failed to read map.html: {exc}")

    @property
    def result(self):
        return self._result

    @property
    def step_index(self):
        return self._step_index

    @property
    def step_count(self):
        return len(self._steps)

    @property
    def is_running(self):
        return self._timer.isActive() or (
            self._js_step_in_flight and not self._is_paused
        )

    @property
    def is_paused(self):
        return self._is_paused

    @property
    def is_manual_mode(self):
        return self._manual_mode

    def _on_load_finished(self, ok):
        self._page_loaded = ok
        if not ok:
            message = "Failed to load map.html"
            print(f"[MapWidget ERROR] {message}")
            self.graph_render_failed.emit(message)
            return

        self.set_theme(self._theme)
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
        if payload is None:
            script = f"{function_name}()"
        else:
            script = f"{function_name}({json.dumps(payload, ensure_ascii=False)})"
        if callback is None:
            self.page().runJavaScript(script)
        else:
            self.page().runJavaScript(script, callback)
        return True

    def _serialize_graph(self, graph):
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

        # A two-way road is stored as two directed adjacency edges. Leaflet only
        # needs one physical line; both algorithm directions point to that line.
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
        self._graph_node_count = len(graph_data["nodes"])
        self._graph_generation += 1
        graph_data["render_token"] = self._graph_generation
        if self._page_loaded:
            self._start_graph_render(graph_data)
        else:
            self._pending_graph_data = graph_data

    def _start_graph_render(self, graph_data):
        token = graph_data["render_token"]
        self._run_js_function("initMap", graph_data)
        QTimer.singleShot(80, lambda: self._poll_graph_render(token))

    def _poll_graph_render(self, token):
        if not self._page_loaded or token != self._graph_generation:
            return

        def handle_state(state):
            if token != self._graph_generation:
                return
            if isinstance(state, dict) and state.get("token") == token:
                error = state.get("error")
                if error:
                    self.graph_render_failed.emit(str(error))
                    return
                if state.get("ready"):
                    # initMap rebuilds the Leaflet layer/index state
                    # asynchronously. Re-apply the latest route selection
                    # before consumers treat this renderer as ready so an
                    # earlier Start/Goal update cannot be lost.
                    self._update_selection()
                    self.graph_ready.emit()
                    return
            QTimer.singleShot(100, lambda: self._poll_graph_render(token))

        self.page().runJavaScript("getGraphRenderState()", handle_state)

    def draw_map_step_by_step(
        self,
        result,
        interval_ms=100,
        target_duration_ms=15000,
        manual_mode=False,
    ):
        self.stop_animation()
        if isinstance(result, SearchResult):
            self._result = result
            self._steps = list(result.steps)
        else:
            self._result = SearchResult(
                path=[],
                steps=list(result or []),
                success=False,
                message="Legacy step data provided.",
            )
            self._steps = self._result.steps

        self._step_index = 0
        self._finished_emitted = False
        self._manual_mode = bool(manual_mode)
        self._is_paused = self._manual_mode
        self._paused_at = time.perf_counter() if self._manual_mode else None
        self._interval_ms = max(0, int(interval_ms))
        self._target_duration_ms = max(0, int(target_duration_ms or 0))
        self._reset_playback_deadline()
        self._recalculate_auto_batch_size()
        token = self._playback_generation

        if not self._steps:
            if self._visual_updates_enabled:
                self._run_js_function("resetVisualization")
            self._emit_finished_once()
            return

        if self._manual_mode:
            self.playback_state_changed.emit("paused")
            self._reset_renderer_then(lambda: None)
        else:
            self.playback_state_changed.emit("running")
            self._reset_renderer_then(
                lambda: self._schedule_next(token, delay=0)
            )

    def _reset_renderer_then(self, callback):
        """Reset the visible map without making playback depend on a hidden page."""
        if self._visual_updates_enabled:
            self._run_js_function(
                "resetVisualization",
                callback=lambda _result: callback(),
            )
            return
        QTimer.singleShot(0, callback)

    def set_interval(self, interval_ms):
        """Backward-compatible one-event cadence configuration."""
        self._manual_mode = False
        self._interval_ms = max(0, int(interval_ms))
        self._target_duration_ms = 0
        self._playback_deadline = None
        self._recalculate_auto_batch_size()

    def set_playback_profile(
        self, interval_ms, target_duration_ms, manual_mode=False
    ):
        self._manual_mode = bool(manual_mode)
        self._interval_ms = max(0, int(interval_ms))
        self._target_duration_ms = max(0, int(target_duration_ms or 0))
        self._reset_playback_deadline()
        if (
            self._manual_mode
            and self._steps
            and self._step_index < len(self._steps)
            and not self._finished_emitted
        ):
            self._timer.stop()
            if not self._is_paused:
                self._is_paused = True
                self._paused_at = time.perf_counter()
                self.playback_state_changed.emit("paused")
            return
        if self._is_paused:
            self._paused_at = time.perf_counter()
        self._recalculate_auto_batch_size()
        if self._timer.isActive() and not self._is_paused:
            self._timer.stop()
            self._schedule_next(delay=0)

    def _reset_playback_deadline(self):
        if self._target_duration_ms > 0:
            self._playback_deadline = (
                time.perf_counter() + self._target_duration_ms / 1000
            )
        else:
            self._playback_deadline = None

    def _recalculate_auto_batch_size(self, observed_update_ms=None):
        remaining = max(0, len(self._steps) - self._step_index)
        if self._interval_ms <= 0 or remaining <= 0:
            self._auto_batch_size = max(1, remaining)
            return
        if self._target_duration_ms <= 0:
            self._auto_batch_size = 1
            return
        remaining_budget_ms = float(self._target_duration_ms)
        if self._playback_deadline is not None:
            remaining_budget_ms = max(
                1.0,
                (self._playback_deadline - time.perf_counter()) * 1000,
            )
        effective_update_ms = max(
            float(self._interval_ms),
            float(observed_update_ms or self._interval_ms),
        )
        target_updates = max(1, int(remaining_budget_ms / effective_update_ms))
        self._auto_batch_size = max(1, math.ceil(remaining / target_updates))

    def _step_as_dict(self, index):
        step = self._steps[index]
        step_dict = step.to_dict() if hasattr(step, "to_dict") else dict(step)
        if step_dict.get("type") == "finish" and self._result is not None:
            step_dict.setdefault("path", list(self._result.path))
            step_dict.setdefault("success", self._result.success)
        step_dict["_index"] = index + 1
        step_dict["_total"] = len(self._steps)
        return step_dict

    def _schedule_next(self, token=None, delay=None):
        token = self._playback_generation if token is None else token
        if (
            token != self._playback_generation
            or self._manual_mode
            or self._is_paused
            or self._step_index >= len(self._steps)
        ):
            return
        self._timer.start(self._interval_ms if delay is None else max(0, delay))

    def _on_timer_timeout(self):
        if self._manual_mode:
            return
        if self._interval_ms == 0:
            self._dispatch_steps(
                len(self._steps) - self._step_index,
                instant=True,
            )
        else:
            self._dispatch_steps(self._auto_batch_size)

    def apply_next_step(self):
        self._dispatch_steps(1)

    def _dispatch_steps(self, batch_size, instant=False):
        if self._js_step_in_flight:
            return
        if self._step_index >= len(self._steps):
            self._emit_finished_once()
            return

        start = self._step_index
        end = min(len(self._steps), start + max(1, batch_size))
        step_dicts = [self._step_as_dict(index) for index in range(start, end)]
        self._step_index = end
        self._js_step_in_flight = True
        self._dispatch_started_at = time.perf_counter()
        token = self._playback_generation
        if instant:
            function_name = "renderInstantResult"
            payload = step_dicts[-1]
        else:
            function_name = "applyStep" if len(step_dicts) == 1 else "applySteps"
            payload = step_dicts[0] if len(step_dicts) == 1 else step_dicts
        if not self._visual_updates_enabled:
            QTimer.singleShot(
                0,
                lambda: self._on_steps_rendered(token, step_dicts),
            )
            return
        self._run_js_function(
            function_name,
            payload,
            callback=lambda _result: self._on_steps_rendered(token, step_dicts),
        )

    def _on_steps_rendered(self, token, step_dicts):
        if token != self._playback_generation:
            return
        self._js_step_in_flight = False
        dispatch_started_at = self._dispatch_started_at
        self._dispatch_started_at = None
        emitted = dict(step_dicts[-1])
        if len(step_dicts) > 1:
            emitted["_batch"] = step_dicts
            emitted["_batch_size"] = len(step_dicts)
        self.step_changed.emit(emitted)

        navigation = self._pending_navigation
        self._pending_navigation = None
        if navigation == "previous":
            self.previous_step()
            return
        if navigation == "next":
            self.next_step()
            return

        if (
            emitted.get("type") == "finish"
            or self._step_index >= len(self._steps)
        ):
            self._emit_finished_once()
        elif not self._is_paused:
            # The selected cadence includes renderer time. The old behavior
            # waited N ms *after* rendering and therefore every speed was much
            # slower than its label on a large map.
            elapsed_ms = 0.0
            if dispatch_started_at is not None:
                elapsed_ms = (time.perf_counter() - dispatch_started_at) * 1000
            self._recalculate_auto_batch_size(observed_update_ms=elapsed_ms)
            remaining_delay = max(0, round(self._interval_ms - elapsed_ms))
            self._schedule_next(token, delay=remaining_delay)

    def _emit_finished_once(self):
        self._timer.stop()
        self._is_paused = False
        if not self._finished_emitted:
            self._finished_emitted = True
            self.playback_state_changed.emit("finished")
            self.animation_finished.emit()

    def stop_animation(self):
        self._timer.stop()
        self._playback_generation += 1
        self._js_step_in_flight = False
        self._is_paused = False
        self._pending_navigation = None
        self._playback_deadline = None
        self._paused_at = None

    def pause_animation(self):
        if self._steps and not self._finished_emitted and not self._is_paused:
            self._timer.stop()
            self._is_paused = True
            self._paused_at = time.perf_counter()
            self.playback_state_changed.emit("paused")

    def resume_animation(self):
        if (
            not self._manual_mode
            and self._is_paused
            and self._step_index < len(self._steps)
        ):
            if self._playback_deadline is not None and self._paused_at is not None:
                self._playback_deadline += time.perf_counter() - self._paused_at
            self._paused_at = None
            self._is_paused = False
            self.playback_state_changed.emit("running")
            if not self._js_step_in_flight:
                self._schedule_next(delay=0)

    def replay_animation(self):
        if not self._steps:
            return
        self.stop_animation()
        self._step_index = 0
        self._finished_emitted = False
        self._is_paused = self._manual_mode
        self._paused_at = time.perf_counter() if self._manual_mode else None
        self._reset_playback_deadline()
        self._recalculate_auto_batch_size()
        token = self._playback_generation
        if self._manual_mode:
            self.playback_state_changed.emit("paused")
            self._reset_renderer_then(lambda: None)
        else:
            self.playback_state_changed.emit("running")
            self._reset_renderer_then(
                lambda: self._schedule_next(token, delay=0)
            )

    def next_step(self):
        if not self._steps or self._step_index >= len(self._steps):
            return
        self._timer.stop()
        self._is_paused = True
        if self._paused_at is None:
            self._paused_at = time.perf_counter()
        self.playback_state_changed.emit("paused")
        if self._js_step_in_flight:
            self._pending_navigation = "next"
            return
        self._dispatch_steps(1)

    def previous_step(self):
        if not self._steps or self._step_index <= 0:
            return
        self._timer.stop()
        self._is_paused = True
        if self._paused_at is None:
            self._paused_at = time.perf_counter()
        self.playback_state_changed.emit("paused")
        if self._js_step_in_flight:
            self._pending_navigation = "previous"
            return

        self._finished_emitted = False
        self._step_index -= 1
        rendered_steps = [
            self._step_as_dict(index) for index in range(self._step_index)
        ]
        self._js_step_in_flight = True
        token = self._playback_generation

        def history_rendered(_result):
            if token != self._playback_generation:
                return
            self._js_step_in_flight = False
            if self._step_index:
                emitted = dict(rendered_steps[-1])
                emitted["_history"] = rendered_steps
                self.step_changed.emit(emitted)
            else:
                self.step_changed.emit(
                    {"type": "reset", "_index": 0, "_total": len(self._steps)}
                )

        visual_snapshot = self._build_visual_snapshot(rendered_steps)
        if self._visual_updates_enabled:
            self._run_js_function("renderSnapshot", visual_snapshot, history_rendered)
        else:
            QTimer.singleShot(0, lambda: history_rendered(None))

    def _build_visual_snapshot(self, steps):
        """Build one bounded map state instead of replaying the whole history."""
        frontier = {}
        explored = {}
        current = None
        edge_states = {}
        path = []

        for step in steps:
            step_type = step.get("type")
            node = step.get("node")
            if step_type == "expand":
                if current:
                    explored[current] = None
                current = node
                frontier.pop(node, None)
                if node:
                    explored[node] = None
            elif step_type in {"discover", "update"}:
                if node and node not in explored:
                    frontier[node] = None
                source, target = step.get("from"), step.get("to")
                if source and target:
                    key = (source, target)
                    edge_states.pop(key, None)
                    edge_states[key] = (
                        "relaxed" if step_type == "update" else "inspect"
                    )
            elif step_type == "finish":
                if current:
                    explored[current] = None
                current = None
                path = list(step.get("path") or [])

        explored_nodes = list(explored)
        edges = [
            {"from": source, "to": target, "state": state}
            for (source, target), state in edge_states.items()
        ]
        if self._graph_node_count > 2000:
            # StatePanel still exposes the complete explored/visited lists. The
            # cap applies only to map markers, where thousands of overlapping
            # points are neither readable nor responsive.
            explored_nodes = explored_nodes[-1000:]
            edges = edges[-1200:]

        return {
            "frontier": list(frontier),
            "explored": explored_nodes,
            "current": current,
            "edges": edges,
            "path": path,
        }

    def reset(self, emit_state=True):
        self.stop_animation()
        self._step_index = 0
        self._result = None
        self._steps.clear()
        self._finished_emitted = False
        if self._visual_updates_enabled:
            self._run_js_function("resetVisualization")
            self._update_selection()
        if emit_state:
            self.playback_state_changed.emit("ready")

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

    def get_endpoint_marker_state(self, callback):
        """Fetch the map endpoint-marker diagnostics from Leaflet."""
        return self._run_js_function("getEndpointMarkerState", callback=callback)

    def set_theme(self, theme_name):
        self._theme = theme_name
        self._run_js_function("setTheme", {"theme": theme_name})

    def set_visual_updates_enabled(self, enabled):
        self._visual_updates_enabled = bool(enabled)
        if self._visual_updates_enabled:
            self.refresh_current_visualization()

    def refresh_current_visualization(self):
        if not self._visual_updates_enabled or not self._steps:
            return
        rendered_steps = [
            self._step_as_dict(index) for index in range(self._step_index)
        ]
        self._run_js_function(
            "renderSnapshot",
            self._build_visual_snapshot(rendered_steps),
        )

    def show_message(self, text, level="info"):
        self._run_js_function("showMapMessage", {"text": text, "level": level})
