import os
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QMenu
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class PlaylistPanel(QListWidget):
    """播放列表面板"""

    # 信号定义
    audio_selected = pyqtSignal(int)  # 选择音频，参数为索引
    playlist_cleared = pyqtSignal()   # 清空播放列表

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("播放列表")

        # 数据
        self.audio_files = []  # 音频文件列表
        self.current_index = -1  # 当前播放索引

        # 播放列表（QListWidget）
        self.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 5px;
                background-color: white;
                outline: none;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:hover {
                background-color: rgba(52, 152, 219, 0.1);
            }
            QListWidget::item:selected {
                background-color: rgba(52, 152, 219, 0.3);
                color: black;
            }
        """)
        self.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def set_playlist(self, audio_files, current_index=-1):
        """设置播放列表"""
        self.audio_files = audio_files
        self.current_index = current_index
        self.refresh_list()

    def refresh_list(self):
        """刷新列表显示"""
        self.clear()

        # 显示全部文件
        for i, file_path in enumerate(self.audio_files):
            file_name = os.path.basename(file_path)

            # 当前播放的文件添加前缀
            if i == self.current_index:
                display_text = f"▶ {file_name}"
            else:
                display_text = file_name

            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, i)  # 存储原始索引

            # 当前播放的文件高亮
            if i == self.current_index:
                font = QFont()
                font.setBold(True)
                item.setFont(font)

            self.addItem(item)

    def update_current_index(self, index):
        """更新当前播放索引"""
        self.current_index = index
        self.refresh_list()

    def on_item_double_clicked(self, item):
        """双击播放"""
        original_index = item.data(Qt.UserRole)
        self.audio_selected.emit(original_index)

    def show_context_menu(self, position):
        """右键菜单"""
        item = self.itemAt(position)
        if not item:
            return

        menu = QMenu(self)

        # 播放动作
        play_action = menu.addAction("▶ 播放")

        # 从列表移除动作
        remove_action = menu.addAction("🗑️ 从列表移除")

        # 显示菜单
        action = menu.exec_(self.mapToGlobal(position))

        if action == play_action:
            # 播放选中的音频
            original_index = item.data(Qt.UserRole)
            self.audio_selected.emit(original_index)
        elif action == remove_action:
            # 从列表移除
            original_index = item.data(Qt.UserRole)
            self.remove_item(original_index)

    def remove_item(self, index):
        """移除单项"""
        if 0 <= index < len(self.audio_files):
            # 移除文件
            removed_file = self.audio_files.pop(index)

            # 调整当前索引
            if index < self.current_index:
                self.current_index -= 1
            elif index == self.current_index:
                # 如果移除的是当前播放的文件，将当前索引设为 -1
                self.current_index = -1

            # 刷新显示
            self.refresh_list()
