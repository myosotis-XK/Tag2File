import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem, QMenu
from src.ui.components.style_utils import create_context_menu

from .audio_theme import LIST_PANEL_STYLE


class PlaylistPanel(QListWidget):
    audio_selected = pyqtSignal(int)
    audio_remove_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio_files = []
        self.current_index = -1
        self.setWindowTitle("播放列表")
        self.setAlternatingRowColors(False)
        self.setUniformItemSizes(False)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setStyleSheet(LIST_PANEL_STYLE)
        self.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def set_playlist(self, audio_files, current_index=-1):
        self.audio_files = list(audio_files)
        self.current_index = current_index
        self.refresh_list()

    def refresh_list(self):
        self.clear()
        for index, file_path in enumerate(self.audio_files):
            file_name = os.path.basename(file_path)
            display_text = f"▶ {file_name}" if index == self.current_index else file_name
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, index)
            if index == self.current_index:
                font = QFont()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(QColor("#1f2d3d"))
                item.setBackground(QColor("#d8ebff"))
            self.addItem(item)

    def update_current_index(self, index):
        self.current_index = index
        self.refresh_list()

    def on_item_double_clicked(self, item):
        self.audio_selected.emit(item.data(Qt.UserRole))

    def show_context_menu(self, position):
        item = self.itemAt(position)
        if not item:
            return

        menu = create_context_menu(self)
        play_action = menu.addAction("播放")
        remove_action = menu.addAction("从列表移除")
        action = menu.exec_(self.mapToGlobal(position))
        item_index = item.data(Qt.UserRole)

        if action == play_action:
            self.audio_selected.emit(item_index)
        elif action == remove_action:
            self.audio_remove_requested.emit(item_index)
