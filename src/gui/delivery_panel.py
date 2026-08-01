from PyQt5.QtWidgets import (
    QGroupBox,
    QLabel,
    QVBoxLayout,
)


class DeliveryPanel(QGroupBox):

    def __init__(self):
        super().__init__("Delivery Information")

        layout = QVBoxLayout(self)

        self.algorithm = QLabel("-")
        self.distance = QLabel("-")
        self.time = QLabel("-")
        self.nodes = QLabel("-")
        self.status = QLabel("Waiting")

        layout.addWidget(QLabel("Algorithm"))
        layout.addWidget(self.algorithm)

        layout.addWidget(QLabel("Distance"))
        layout.addWidget(self.distance)

        layout.addWidget(QLabel("Estimated Time"))
        layout.addWidget(self.time)

        layout.addWidget(QLabel("Visited Nodes"))
        layout.addWidget(self.nodes)

        layout.addWidget(QLabel("Status"))
        layout.addWidget(self.status)

        layout.addStretch()
