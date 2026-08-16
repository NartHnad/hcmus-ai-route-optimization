"""QWebChannel bridge shared by the map and graph edge editors."""

from PyQt5.QtCore import QObject, QVariant, pyqtSlot


class EdgeEditorBridge(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._update_handler = None

    def set_update_handler(self, handler):
        self._update_handler = handler

    @pyqtSlot(QVariant, result=QVariant)
    def updateEdge(self, payload):
        if self._update_handler is None:
            return {"ok": False, "error": "Edge editing is not available."}
        try:
            result = self._update_handler(dict(payload or {}))
            return result if isinstance(result, dict) else {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
