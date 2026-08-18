import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import QApplication

from src.gui.node_search_combo import NodeSearchComboBox, normalize_search_text


def _combo(entries):
    app = QApplication.instance() or QApplication([])
    combo = NodeSearchComboBox()
    model = QStandardItemModel(combo)
    search_entries = []
    for node_id, name in entries:
        display = f"{node_id} · {name}"
        item = QStandardItem(display)
        item.setData(node_id, Qt.UserRole)
        model.appendRow(item)
        search_entries.append((node_id, name, display))
    combo.setModel(model)
    combo.set_search_entries(search_entries)
    combo.setCurrentIndex(0 if entries else -1)
    return app, combo


def test_node_search_is_case_and_accent_insensitive():
    assert normalize_search_text("Bến Thành") == "ben thanh"
    _app, combo = _combo(
        [
            ("N6", "Saigon Centre"),
            ("N7", "Bến Thành Market"),
            ("N8", "Bệnh viện Quận 1"),
        ]
    )
    try:
        assert combo.isEditable()
        assert combo.ranked_node_ids("n7")[0] == "N7"
        assert combo.ranked_node_ids("BEN THANH")[0] == "N7"
        assert combo.ranked_node_ids("benh vien")[0] == "N8"
    finally:
        combo.close()


def test_node_search_commits_the_closest_typo_match():
    _app, combo = _combo(
        [
            ("N6", "Saigon Centre"),
            ("N7", "Bến Thành Market"),
            ("N8", "Independence Palace"),
        ]
    )
    try:
        combo.lineEdit().setText("saigon centar")
        assert combo.currentData() is None
        assert combo.commit_best_match()
        assert combo.currentData() == "N6"
        assert combo.currentText() == "N6 · Saigon Centre"
    finally:
        combo.close()


def test_node_search_caps_the_popup_model_for_large_node_sets():
    entries = [(str(index), f"Node {index}") for index in range(1500)]
    _app, combo = _combo(entries)
    try:
        results = combo.ranked_node_ids("node 14")
        assert results[0] == "14"
        assert len(results) == combo.SUGGESTION_LIMIT

        combo.lineEdit().setText("node 14")
        combo._refresh_suggestions()
        assert combo._suggestion_model.rowCount() == combo.SUGGESTION_LIMIT
        assert combo._suggestion_model.rowCount() < combo.count()
    finally:
        combo.close()


def test_node_search_arrow_opens_the_complete_node_list():
    _app, combo = _combo(
        [
            ("N1", "First node"),
            ("N2", "Second node"),
        ]
    )
    try:
        combo.showPopup()
        assert combo.view().isVisible()
        assert combo.view().model().rowCount() == combo.count()
    finally:
        combo.hidePopup()
        combo.close()
