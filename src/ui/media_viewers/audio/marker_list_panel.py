from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem, QMenu
from src.ui.components.style_utils import create_context_menu

from .audio_utils import marker_display_text, sort_markers
from .audio_theme import LIST_PANEL_STYLE


class MarkerListPanel(QListWidget):
    marker_clicked = pyqtSignal(int)
    marker_edit_requested = pyqtSignal(dict)
    marker_delete_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.markers_data = []
        self.setIconSize(QSize(12, 32))
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setStyleSheet(LIST_PANEL_STYLE)
        self.itemDoubleClicked.connect(self.on_marker_double_clicked)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def set_markers(self, markers):
        self.clear()
        self.markers_data = sort_markers(markers)

        for marker in self.markers_data:
            item = QListWidgetItem(marker_display_text(marker))
            item.setIcon(self._create_marker_color_icon(marker.get('color', '#3498db')))
            item.setData(Qt.UserRole, marker)
            self.addItem(item)

    def _create_marker_color_icon(self, color):
        pixmap = QPixmap(12, 32)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(3, 3, 5, 26, 2, 2)
        painter.end()

        return QIcon(pixmap)

    def on_marker_double_clicked(self, item):
        marker = item.data(Qt.UserRole)
        if marker:
            self.marker_clicked.emit(marker['id'])

    def show_context_menu(self, position):
        item = self.itemAt(position)
        if not item:
            return

        marker = item.data(Qt.UserRole)
        if not marker:
            return

        menu = create_context_menu(self)
        edit_action = menu.addAction("编辑")
        delete_action = menu.addAction("删除")
        action = menu.exec_(self.mapToGlobal(position))

        if action == edit_action:
            self.marker_edit_requested.emit(dict(marker))
        elif action == delete_action:
            self.marker_delete_requested.emit(marker['id'])
