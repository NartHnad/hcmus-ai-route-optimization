# src/gui/main_window.py

import os
import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Set up python paths to import modules from src/ regardless of invocation path
CURRENT_DIR = Path(__file__).resolve().parent
SRC_DIR = CURRENT_DIR.parent
PROJECT_ROOT = SRC_DIR.parent

if os.fspath(SRC_DIR) not in sys.path:
    sys.path.insert(0, os.fspath(SRC_DIR))
if os.fspath(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, os.fspath(PROJECT_ROOT))

try:
    from algorithms.mock_algorithm import mock_search
    from gui.map_widget import MapWidget
    from models.graph_factory import build_graph
except ImportError:
    from src.algorithms.mock_algorithm import mock_search
    from src.gui.map_widget import MapWidget
    from src.models.graph_factory import build_graph


class MainWindow(QMainWindow):
    """
    The main window containing the search controls panel on the left
    and the interactive Leaflet map widget on the right.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Route Optimization Visualizer")
        self.resize(1100, 750)

        self.graph = None

        # Setup main container layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Control Panel layout (Sidebar)
        sidebar = QWidget()
        sidebar.setFixedWidth(280)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(16)

        # 1. Dataset controls group
        dataset_group = QGroupBox("Dataset Control")
        dataset_layout = QVBoxLayout(dataset_group)

        dataset_layout.addWidget(QLabel("Select Dataset:"))
        self.dataset_combo = QComboBox()
        # Dynamically load all JSON files from the data folder
        data_dir = PROJECT_ROOT / "data"
        json_files = [f.name for f in data_dir.glob("*.json")] if data_dir.exists() else []
        if not json_files:
            json_files = ["No datasets found"]
        self.dataset_combo.addItems(json_files)
        dataset_layout.addWidget(self.dataset_combo)

        self.load_button = QPushButton("Load Graph Data")
        self.load_button.clicked.connect(self.on_load_graph_clicked)
        dataset_layout.addWidget(self.load_button)

        sidebar_layout.addWidget(dataset_group)

        # 2. Pathfinding setup controls group
        pathfinding_group = QGroupBox("Pathfinding Setup")
        pathfinding_layout = QVBoxLayout(pathfinding_group)

        pathfinding_layout.addWidget(QLabel("Start Node:"))
        self.start_combo = QComboBox()
        pathfinding_layout.addWidget(self.start_combo)

        pathfinding_layout.addWidget(QLabel("Goal Node:"))
        self.goal_combo = QComboBox()
        pathfinding_layout.addWidget(self.goal_combo)

        self.run_button = QPushButton("Run Mock Search")
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self.on_run_search_clicked)
        pathfinding_layout.addWidget(self.run_button)

        self.reset_button = QPushButton("Reset Map Style")
        self.reset_button.setEnabled(False)
        self.reset_button.clicked.connect(self.on_reset_clicked)
        pathfinding_layout.addWidget(self.reset_button)

        sidebar_layout.addWidget(pathfinding_group)

        # 3. Status display group
        status_group = QGroupBox("Status Console")
        status_layout = QVBoxLayout(status_group)
        self.status_label = QLabel("Please load a graph dataset.")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignTop)
        status_layout.addWidget(self.status_label)
        sidebar_layout.addWidget(status_group)

        sidebar_layout.addStretch()
        main_layout.addWidget(sidebar)

        # Map display widget (Embedded Chromium browser with Leaflet.js)
        self.map_widget = MapWidget()
        main_layout.addWidget(self.map_widget, stretch=1)

    def on_load_graph_clicked(self):
        filename = self.dataset_combo.currentText()
        json_path = PROJECT_ROOT / "data" / filename

        if not json_path.exists():
            self.status_label.setText(f"Error: {filename} does not exist at expected path {json_path}")
            return

        try:
            self.graph = build_graph(os.fspath(json_path))
            self.map_widget.draw_graph(self.graph)

            node_ids = sorted(list(self.graph.nodes.keys()))
            self.start_combo.clear()
            self.start_combo.addItems(node_ids)
            self.goal_combo.clear()
            self.goal_combo.addItems(node_ids)

            if len(node_ids) >= 2:
                self.start_combo.setCurrentIndex(0)
                self.goal_combo.setCurrentIndex(len(node_ids) - 1)

            self.run_button.setEnabled(True)
            self.reset_button.setEnabled(True)

            total_edges = sum(len(edges) for edges in self.graph.adjacency_list.values())
            self.status_label.setText(
                f"Successfully loaded {filename}.\n\n"
                f"Nodes count: {len(self.graph.nodes)}\n"
                f"Edges count: {total_edges}"
            )
        except Exception as e:
            self.status_label.setText(f"Failed to load graph: {str(e)}")

    def on_run_search_clicked(self):
        if self.graph is None:
            return

        start_id = self.start_combo.currentText()
        goal_id = self.goal_combo.currentText()

        if not start_id or not goal_id:
            self.status_label.setText("Error: start or goal node selection is invalid.")
            return

        self.status_label.setText(f"Running mock pathfinding from {start_id} to {goal_id}...")

        result = mock_search(self.graph, start_id, goal_id)
        self.map_widget.draw_map_step_by_step(result, interval_ms=500)

    def on_reset_clicked(self):
        self.map_widget.reset()
        self.status_label.setText("Map style reset to default.")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
