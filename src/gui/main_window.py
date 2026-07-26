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

        main_layout = QHBoxLayout(central_widget)

        main_layout.addWidget(self.create_sidebar())

        self.map_widget = MapWidget()
        main_layout.addWidget(self.map_widget, stretch=1)

        # Initial message
        self.log_status("[INFO] Application started.")
        self.log_status("[INFO] Please load a dataset.")


    def setup_window(self):
        self.setWindowTitle("Route Optimization Visualizer")
        self.resize(1100, 750)
    
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

        parameter_layout.addWidget(self.start_combo)

        # Goal Node
        parameter_layout.addWidget(QLabel("Goal Node"))

        self.goal_combo = QComboBox()

        parameter_layout.addWidget(self.goal_combo)

        # Animation Speed
        parameter_layout.addWidget(QLabel("Animation Speed"))

        self.speed_combo = QComboBox()

        self.speed_combo.addItems(["100 ms", "250 ms", "500 ms", "1000 ms"])

        # self.speed_combo.setCurrentText("500 ms")

        parameter_layout.addWidget(self.speed_combo)

        return parameter_group

    def create_execution_group(self):
        execution_group = QGroupBox("Execution")

        execution_layout = QVBoxLayout(execution_group)

        self.run_button = QPushButton("Run Search")
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self.on_run_search_clicked)
        execution_layout.addWidget(self.run_button)

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
            node_ids = sorted(list(self.graph.nodes.keys()))

            self.start_combo.clear()
            self.start_combo.addItems(node_ids)

            self.goal_combo.clear()
            self.goal_combo.addItems(node_ids)

            # Set default start and goal nodes
            if len(node_ids) >= 2:
                self.start_combo.setCurrentIndex(0)
                self.goal_combo.setCurrentIndex(len(node_ids) - 1)

            # Enable pathfinding controls
            self.run_button.setEnabled(True)
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

        # Get interval from animation speed
        interval = int(self.speed_combo.currentText().split()[0])

        # Animate the search process on the map
        self.map_widget.draw_map_step_by_step(result, interval)

    # ======================================================
    # Restore the map to its original appearance.
    # ======================================================
    def on_reset_clicked(self):
        self.map_widget.reset()
        self.log_status("[INFO] Map style reset to default.")

    def log_status(self, message: str):
        """
        Append a message to the status console.
        """

        self.status_console.appendPlainText(message)

        scrollbar = self.status_console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


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
