import os
from types import SimpleNamespace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.gui.graph_widget import GraphWidget
from src.gui.map_widget import MapWidget


def test_map_html_uses_qt_webengine_compatible_string_replacement():
    map_html = (
        Path(__file__).resolve().parents[1] / "src" / "gui" / "assets" / "map.html"
    ).read_text(encoding="utf-8")

    assert ".replaceAll(" not in map_html
    assert ".replace(/&/g, '&amp;')" in map_html


class _SignalRecorder:
    def __init__(self, events, name):
        self._events = events
        self._name = name

    def emit(self, *_args):
        self._events.append(self._name)


def _selection_harness(widget_type):
    harness = SimpleNamespace(
        _current_start=None,
        _current_goals=[],
        _display_goal_order=[],
        _preview_goal=None,
        calls=[],
    )

    def run_js(function_name, payload=None, callback=None):
        harness.calls.append((function_name, payload))
        if callback is not None:
            callback(None)
        return True

    harness._run_js_function = run_js
    harness._update_selection = lambda: widget_type._update_selection(harness)
    return harness


def test_map_and_graph_widgets_share_the_multi_location_selection_payload():
    expected_payload = {
        "start": "S",
        "goals": ["G2", "G1"],
        "display_order": ["G1", "G2"],
        "preview_goal": "G3",
    }

    for widget_type in (MapWidget, GraphWidget):
        harness = _selection_harness(widget_type)
        widget_type.set_route_locations(
            harness,
            "S",
            ["G2", "G1"],
            ["G1", "G2"],
            "G3",
        )

        assert harness.calls[-1] == ("updateSelection", expected_payload)


def test_map_reapplies_selection_before_emitting_graph_ready():
    events = []
    token = 7

    class _Page:
        @staticmethod
        def runJavaScript(_script, callback):
            events.append("render-state")
            callback({"token": token, "ready": True, "error": None})

    harness = SimpleNamespace(
        _page_loaded=True,
        _graph_generation=token,
        page=lambda: _Page(),
        _update_selection=lambda: events.append("selection"),
        graph_ready=_SignalRecorder(events, "ready"),
        graph_render_failed=_SignalRecorder(events, "failed"),
    )

    MapWidget._poll_graph_render(harness, token)

    assert events == ["render-state", "selection", "ready"]


def test_graph_reapplies_selection_before_emitting_graph_ready():
    events = []
    token = 11

    def run_js(function_name, payload=None, callback=None):
        events.append(function_name)
        callback({"ready": True, "token": token})
        return True

    harness = SimpleNamespace(
        _graph_generation=token,
        _run_js_function=run_js,
        _update_selection=lambda: events.append("selection"),
        graph_ready=_SignalRecorder(events, "ready"),
        graph_render_failed=_SignalRecorder(events, "failed"),
    )

    GraphWidget._start_graph_render(harness, {"render_token": token})

    assert events == ["initGraph", "selection", "ready"]
