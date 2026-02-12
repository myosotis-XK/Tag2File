from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QMessageBox, QMenu
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor


def format_time(ms):
    """格式化毫秒为 mm:ss 格式"""
    from PyQt5.QtCore import QTime
    time = QTime(0, 0).addMSecs(ms)
    return time.toString("mm:ss")


class MarkerListPanel(QListWidget):
    """标记列表面板"""

    # 信号定义
    marker_clicked = pyqtSignal(int)  # 点击标记时发出，参数为标记ID
    marker_edited = pyqtSignal(int)   # 编辑标记时发出，参数为标记ID
    marker_deleted = pyqtSignal(int)  # 删除标记时发出，参数为标记ID

    def __init__(self, audio_file_path=None, parent=None):
        """
        初始化标记列表面板

        :param audio_file_path: 音频文件路径（normalize_path_lowercase 处理后）
        :param parent: 父窗口
        """
        super().__init__(parent)
        self.audio_file_path = audio_file_path
        self.markers_data = []  # 存储从数据库加载的标记数据
        self.max_duration_ms = None  # 音频最大时长
        self.main_window = None  # 主窗口引用

        self.init_ui()
        if self.audio_file_path:
            self.load_markers()

    def init_ui(self):
        """初始化UI"""
        # 设置样式
        self.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 3px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background-color: #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)

        # 双击跳转到标记位置
        self.itemDoubleClicked.connect(self.on_marker_double_clicked)

        # 右键菜单
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def set_audio_file_path(self, path):
        """设置音频文件路径并重新加载标记"""
        self.audio_file_path = path
        self.load_markers()

    def set_max_duration(self, duration_ms):
        """设置音频最大时长"""
        self.max_duration_ms = duration_ms

    def set_main_window(self, window):
        """设置主窗口引用"""
        self.main_window = window

    def load_markers(self):
        """从数据库加载标记"""
        self.clear()
        self.markers_data = []

        if not self.audio_file_path:
            return

        try:
            from src.core.DictManage import DictManage

            dict_manage = DictManage()
            self.markers_data = dict_manage.get_audio_markers(self.audio_file_path)

            # 按时间排序
            self.markers_data.sort(key=lambda m: m.get('time', 0) if m['type'] == 0 else m.get('start', 0))

            for marker in self.markers_data:
                item = QListWidgetItem()

                # 格式化显示文本
                if marker['type'] == 0:  # 点标记
                    time_str = format_time(marker['time'])
                    display_text = f"{time_str} - {marker['label']}"
                else:  # 范围标记
                    start_str = format_time(marker['start'])
                    end_str = format_time(marker['end'])
                    display_text = f"{start_str}-{end_str} - {marker['label']}"

                item.setText(display_text)

                # 设置背景色（使用标记颜色的浅色版本）
                color = QColor(marker['color'])
                color.setAlpha(50)
                item.setBackground(color)

                # 存储标记数据
                item.setData(Qt.UserRole, marker)

                self.addItem(item)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载标记失败:\n{str(e)}")

    def on_marker_double_clicked(self, item):
        """双击标记时跳转到对应时间"""
        marker = item.data(Qt.UserRole)
        if marker:
            marker_id = marker['id']
            self.marker_clicked.emit(marker_id)

    def show_context_menu(self, position):
        """显示右键菜单"""
        item = self.itemAt(position)
        if not item:
            return

        marker = item.data(Qt.UserRole)
        if not marker:
            return

        menu = QMenu(self)

        edit_action = menu.addAction("📝 编辑")
        delete_action = menu.addAction("🗑️ 删除")

        action = menu.exec_(self.mapToGlobal(position))

        if action == edit_action:
            self.edit_marker(marker)
        elif action == delete_action:
            self.delete_marker(marker)

    def edit_marker(self, marker):
        """编辑标记（调用主窗口的统一方法）"""
        if self.main_window:
            self.main_window.edit_marker(marker)

    def delete_marker(self, marker):
        """删除标记"""
        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除标记 '{marker.get('label', '未命名')}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                from src.core.DictManage import DictManage

                dict_manage = DictManage()
                dict_manage.delete_audio_marker(self.audio_file_path, marker['id'])

                # 刷新列表
                self.load_markers()

                # 发出删除信号
                self.marker_deleted.emit(marker['id'])

                QMessageBox.information(self, "成功", "标记已删除")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除标记失败:\n{str(e)}")


if __name__ == "__main__":
    """测试代码"""
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 需要实际的音频文件路径进行测试
    # panel = MarkerListPanel(audio_file_path="your/audio/file/path")
    panel = MarkerListPanel()
    panel.resize(300, 400)
    panel.show()

    sys.exit(app.exec_())
