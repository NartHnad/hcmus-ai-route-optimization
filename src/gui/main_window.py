# src/gui/main_window.py

# Import standard Python libraries
import sys

# Import PyQt5 modules for building the graphical interface
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
    QPlainTextEdit,  # Using for display searching process (log):
)

# Import project modules.
from src.algorithms.algorithms import run_algorithm, get_algorithms
from src.gui.map_widget import MapWidget
from src.data.data_loader import load_dataset, get_json_datasets
from src.utils.node_visibility import is_visible_node  # #NhatHuyChanged

from pathlib import Path


class MainWindow(QMainWindow):
    """
    The main window containing the search controls panel on the left
    and the interactive Leaflet map widget on the right.

    The window contains:
        - A control sidebar
        - An interactive Leaflet map
        - A status console
    """

    def __init__(self):
        super().__init__()

        # Configure the main window
        self.setup_window()

        # Store the currently loaded graph
        self.graph = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Mobile Mode
        self.mobile_mode = False

        # ===========================
        # Main Layout (Vertical)
        # ===========================
        self.main_layout = QVBoxLayout(central_widget)

        # Header
        header = self.create_header_group()
        self.main_layout.addWidget(header)

        # ===========================
        # Content Layout (Horizontal)
        # ===========================
        self.content_layout = QHBoxLayout()

        # Sidebar
        self.sidebar = self.create_sidebar()
        self.content_layout.addWidget(self.sidebar)

        # Map
        self.map_widget = MapWidget()
        self.content_layout.addWidget(self.map_widget, stretch=1)

        # Add content to main layout
        self.main_layout.addLayout(self.content_layout)

        # Mobile Panel
        self.mobile_panel = self.create_mobile_panel()
        self.mobile_panel.hide()
        # Add mobile Panel to main layout
        self.main_layout.addWidget(self.mobile_panel)

        # Signals
        self.map_widget.animation_finished.connect(self.on_animation_finished)

        self.map_widget.step_changed.connect(self.on_step_changed)

        # Initial message
        self.log_status("[INFO] Application started.")
        self.log_status("[INFO] Please load a dataset.")

    def setup_window(self):
        self.setWindowTitle("Route Optimization Visualizer")

        self.load_theme("light")

        self.resize(1100, 750)

    def create_header_group(self):
        """
        Create the application header containing the title
        and the light/dark theme switch buttons.
        """

        header_widget = QWidget()

        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 8, 10, 8)
        header_layout.setSpacing(10)

        # -------------------------
        # Application title
        # -------------------------
        title_label = QLabel("Route Optimization Visualizer")

        title_font = title_label.font()
        title_font.setPointSize(14)
        title_font.setBold(True)

        title_label.setFont(title_font)

        # -------------------------
        # Theme buttons
        # -------------------------
        self.light_button = QPushButton("Light Mode")
        self.dark_button = QPushButton("Dark Mode")

        self.light_button.clicked.connect(lambda: self.load_theme("light"))

        self.dark_button.clicked.connect(lambda: self.load_theme("dark"))

        self.mobile_button = QPushButton("📱 Mobile")

        # -------------------------
        # Device buttons
        # -------------------------
        self.mobile_button.clicked.connect(self.toggle_mobile_mode)

        # -------------------------
        # Layout
        # -------------------------
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        header_layout.addWidget(self.light_button)
        header_layout.addWidget(self.dark_button)

        header_layout.addWidget(self.mobile_button)

        return header_widget

    def create_sidebar(self):
        # Control Panel layout (Sidebar)
        sidebar = QWidget()
        sidebar.setFixedWidth(280)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(16)

        sidebar_layout.addWidget(self.create_dataset_group())
        sidebar_layout.addWidget(self.create_algorithm_group())
        sidebar_layout.addWidget(self.create_parameters_group())
        sidebar_layout.addWidget(self.create_execution_group())
        sidebar_layout.addWidget(self.create_status_group())

        sidebar_layout.addStretch()

        return sidebar

    def create_mobile_panel(self):

        panel = QGroupBox("Delivery Information")

        layout = QVBoxLayout(panel)

        self.mobile_start = QLabel("Start : -")
        self.mobile_goal = QLabel("Goal : -")
        self.mobile_algorithm = QLabel("Algorithm : -")
        self.mobile_status = QLabel("Status : Ready")

        layout.addWidget(self.mobile_start)
        layout.addWidget(self.mobile_goal)
        layout.addWidget(self.mobile_algorithm)
        layout.addWidget(self.mobile_status)

        return panel

    def create_dataset_group(self):
        dataset_group = QGroupBox("Dataset Control")
        dataset_layout = QVBoxLayout(dataset_group)

        dataset_layout.addWidget(QLabel("Select Dataset:"))
        self.dataset_combo = QComboBox()

        # GET DATASET TO SELECT
        available_datasets = get_json_datasets()

        """
        Check available Datasets
        """
        if available_datasets:
            self.dataset_combo.addItems(available_datasets)
        else:
            self.dataset_combo.addItem("Not found any datasets!")
            self.dataset_combo.setEnabled(False)

        dataset_layout.addWidget(self.dataset_combo)

        self.load_button = QPushButton("Load Graph Data")
        self.load_button.clicked.connect(self.on_load_graph_clicked)
        dataset_layout.addWidget(self.load_button)

        return dataset_group

    def create_algorithm_group(self):
        algorithm_group = QGroupBox("Algorithm")
        algorithm_layout = QVBoxLayout(algorithm_group)

        algorithm_layout.addWidget(QLabel("Select Algorithm:"))

        self.algorithm_combo = QComboBox()

        # Algorithm selection
        self.available_algorithms = get_algorithms()

        if self.available_algorithms:
            self.algorithm_combo.addItems(self.available_algorithms)
        else:
            self.algorithm_combo.addItem("Not found any algorithms!")
            self.algorithm_combo.setEnabled(False)

        algorithm_layout.addWidget(self.algorithm_combo)

        return algorithm_group

    def create_parameters_group(self):
        parameter_group = QGroupBox("Parameters")
        parameter_layout = QVBoxLayout(parameter_group)

        # Start Node
        parameter_layout.addWidget(QLabel("Start Node"))

        self.start_combo = QComboBox()

        # When changes Start --> Highlight Node
        self.start_combo.currentTextChanged.connect(self.on_start_changed)

        parameter_layout.addWidget(self.start_combo)

        # Goal Node
        parameter_layout.addWidget(QLabel("Goal Node"))

        self.goal_combo = QComboBox()

        # When changes Goal
        self.goal_combo.currentTextChanged.connect(self.on_goal_changed)

        parameter_layout.addWidget(self.goal_combo)

        # Animation Speed
        parameter_layout.addWidget(QLabel("Animation Speed"))

        self.speed_combo = QComboBox()

        self.speed_combo.addItems(["0 ms", "100 ms", "250 ms", "500 ms", "1000 ms"])

        # self.speed_combo.setCurrentText("500 ms")

        parameter_layout.addWidget(self.speed_combo)

        return parameter_group

    def create_execution_group(self):
        execution_group = QGroupBox("Execution")
        execution_layout = QVBoxLayout(execution_group)

        # Run
        self.run_button = QPushButton("Run")
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self.on_run_search_clicked)
        execution_layout.addWidget(self.run_button)

        # Pause
        self.pause_button = QPushButton("Pause")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.on_pause_clicked)
        execution_layout.addWidget(self.pause_button)

        # Resume
        self.resume_button = QPushButton("Resume")
        self.resume_button.setEnabled(False)
        self.resume_button.clicked.connect(self.on_resume_clicked)
        execution_layout.addWidget(self.resume_button)

        # Next Step
        self.next_button = QPushButton("Next Step")
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self.on_next_clicked)
        execution_layout.addWidget(self.next_button)

        # Replay
        self.replay_button = QPushButton("Replay")
        self.replay_button.setEnabled(False)
        self.replay_button.clicked.connect(self.on_replay_clicked)
        execution_layout.addWidget(self.replay_button)

        # Reset
        self.reset_button = QPushButton("Reset Map")
        self.reset_button.setEnabled(False)
        self.reset_button.clicked.connect(self.on_reset_clicked)
        execution_layout.addWidget(self.reset_button)

        return execution_group

    def create_status_group(self):
        status_group = QGroupBox("Status")

        status_layout = QVBoxLayout(status_group)

        self.status_console = QPlainTextEdit()

        # Status console is read-only
        self.status_console.setReadOnly(True)

        # limit height
        self.status_console.setMaximumHeight(180)

        status_layout.addWidget(self.status_console)

        return status_group

    # ==========================================================
    # Load the selected graph dataset.
    #
    # Steps:
    #   1. Read JSON file.
    #   2. Build Graph object.
    #   3. Display graph on map.
    #   4. Populate node selection boxes.
    # ==========================================================
    def on_load_graph_clicked(self):
        filename = self.dataset_combo.currentText()

        try:
            # Construct Graph object from JSON file
            self.graph = load_dataset(filename)

            # Draw graph on the Leaflet map
            self.map_widget.draw_graph(self.graph)

            # Populate node selection boxes
            # #NhatHuyChanged: only selectable nodes with real display names.
            node_ids = sorted(
                node_id
                for node_id, node in self.graph.nodes.items()
                if is_visible_node(node)
            )
            hidden_nodes = len(self.graph.nodes) - len(node_ids)  # #NhatHuyChanged

            self.start_combo.clear()
            self.start_combo.addItems(node_ids)

            self.goal_combo.clear()
            self.goal_combo.addItems(node_ids)

            # Set default start and goal nodes
            if len(node_ids) >= 2:
                self.start_combo.setCurrentIndex(0)
                self.goal_combo.setCurrentIndex(len(node_ids) - 1)

            # Enable execution controls
            self.run_button.setEnabled(len(node_ids) >= 2)  # #NhatHuyChanged

            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(False)
            self.next_button.setEnabled(False)
            self.replay_button.setEnabled(False)

            self.reset_button.setEnabled(True)

            # Count graph edges
            total_edges = sum(
                len(edges) for edges in self.graph.adjacency_list.values()
            )

            # Count Algorithm selections
            total_algorithms = len(self.available_algorithms)

            # Display graph summary
            self.log_status(
                "[INFO]\n"
                f"Successfully loaded {filename}.\n\n"
                f"Nodes count: {len(self.graph.nodes)}\n"
                f"Visible named nodes: {len(node_ids)}\n"  # #NhatHuyChanged
                f"Hidden unnamed nodes: {hidden_nodes}\n"  # #NhatHuyChanged
                f"Edges count: {total_edges}\n"
                f"Algorithms count: {total_algorithms}"
            )

        except Exception as e:
            self.log_status(f"[ERROR] Failed to load graph: {str(e)}")

    # ==========================================================
    # Execute the selected search algorithm.
    #
    # The generated search steps are passed to the map widget
    # for animated visualization.
    # ==========================================================
    def on_run_search_clicked(self):
        if self.graph is None:
            return

        self.map_widget.reset()

        start_id = self.start_combo.currentText()
        goal_id = self.goal_combo.currentText()
        algorithm_name = self.algorithm_combo.currentText()

        # Validate user selections
        if not start_id or not goal_id:
            self.log_status("[ERROR] start or goal node selection is invalid.")
            return

        self.log_status(
            f"[INFO] Running {self.algorithm_combo.currentText()} pathfinding from {start_id} to {goal_id}..."
        )

        # Execute search algorithm
        algorithm = self.algorithm_combo.currentText()
        result = run_algorithm(algorithm, self.graph, start_id, goal_id)

        # # For debug
        # for step in result.steps[:5]:
        #     print(step.to_dict())

        # Get interval from animation speed
        interval = int(self.speed_combo.currentText().split()[0])

        # Animate the search process on the map
        self.map_widget.draw_map_step_by_step(result, interval)

        # Enable Execution Controls
        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)

        self.next_button.setEnabled(True)
        self.replay_button.setEnabled(True)

        self.run_button.setEnabled(False)

    # ======================================================
    # Execution Controls.
    # ======================================================
    def on_pause_clicked(self):
        self.map_widget.pause_animation()

        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(True)

        self.log_status("[INFO] Animation paused.")

    def on_resume_clicked(self):
        self.map_widget.resume_animation()

        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)

        self.log_status("[INFO] Animation resumed.")

    def on_next_clicked(self):
        self.map_widget.next_step()

        self.log_status("[INFO] Execute one animation step.")

    def on_replay_clicked(self):
        self.map_widget.replay_animation()

        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)

        self.log_status("[INFO] Replay animation.")

    def on_reset_clicked(self):
        self.map_widget.reset()

        self.run_button.setEnabled(True)

        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.replay_button.setEnabled(False)

        self.log_status("[INFO] Map style reset to default.")

    def on_animation_finished(self):

        self.log_status("[INFO] Search completed.")

        self.run_button.setEnabled(True)

        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(False)

    def on_step_changed(self, step):

        if "node" in step:
            self.log_status(f"[STEP] Visiting node: {step['node']}")

    def on_start_changed(self, node_id):
        if self.graph is None or not node_id:
            return

        self.map_widget.set_start_node(node_id)
        self.log_status(f"[INFO] Start node selected: {node_id}")

    def on_goal_changed(self, node_id):
        if self.graph is None or not node_id:
            return

        self.map_widget.set_goal_node(node_id)
        self.log_status(f"[INFO] Goal node selected: {node_id}")

    def log_status(self, message: str):
        """
        Append a message to the status console.
        """

        self.status_console.appendPlainText(message)

        scrollbar = self.status_console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def load_theme(self, theme_name):
        theme_path = Path(__file__).resolve().parent / "themes" / f"{theme_name}.qss"

        with open(theme_path, encoding="utf-8") as f:
            self.setStyleSheet(f.read())

    # =======================================
    # MOBILE MODE
    # =======================================
    def toggle_mobile_mode(self):
        if self.mobile_mode:
            self.exit_mobile_mode()
        else:
            self.enter_mobile_mode()

        self.mobile_mode = not self.mobile_mode

    def enter_mobile_mode(self):
        self.sidebar.hide()

        self.mobile_panel.show()

        self.mobile_button.setText("Desktop")

        self.mobile_panel.setMaximumHeight(180)

        self.resize(430, 850)

    def exit_mobile_mode(self):
        self.sidebar.show()

        self.mobile_panel.hide()

        self.mobile_button.setText("Mobile")


# ==========================================================
# Application entry point
#
# Creates the QApplication object,
# initializes the main window,
# and starts the Qt event loop.
# ==========================================================
def main():

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


# Run the application only when this file
# is executed directly.
if __name__ == "__main__":
    main()
