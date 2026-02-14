from PyQt5.QtWidgets import QWidget, QLabel, QMenu
from PyQt5.QtCore import Qt, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QMouseEvent

from src.core.DictManage import DictManage
from .marker_edit_dialog import MarkerEditDialog
from .play_back_slider import format_time

class MarkerDisplayWidget(QWidget):
    """标记显示组件 - 负责标记显示、编辑和跳转"""

    # 信号：当点击标记跳转时发出
    markerJumped = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.DictManage = DictManage()
        self.setMouseTracking(True)
        self.markers = []
        self.snap_threshold = 15
        self.duration_ms = 0  # 音频总时长

        # 设置固定高度
        self.setFixedHeight(30)

        # 设置样式
        self.setStyleSheet("""
            MarkerDisplayWidget {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 3px;
            }
        """)

        # 顶层悬浮标签 (显示描述 + 时间)
        self.floating_label = QLabel(self, Qt.ToolTip)
        self.floating_label.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.floating_label.setStyleSheet("""
            background-color: #34495e;
            color: #ecf0f1;
            padding: 5px 10px;
            border-radius: 4px;
            font-family: 'Segoe UI', 'Microsoft YaHei';
            font-size: 11px;
        """)
        self.floating_label.hide()

        # 音频文件路径（用于保存标记到数据库）
        self.audio_file_path = None

        # 标记列表面板引用（需要从外部设置）
        self.marker_list_panel = None

        # 主窗口引用（用于调用统一的编辑方法）
        self.main_window = None

    def set_duration(self, duration_ms):
        """设置音频总时长"""
        self.duration_ms = duration_ms
        self.update()

    def set_markers(self, markers):
        """设置标记数据"""
        self.markers = markers
        self.update()

    def set_audio_file_path(self, path):
        """设置音频文件路径（用于数据库操作）"""
        self.audio_file_path = path

    def set_marker_list_panel(self, panel):
        """设置标记列表面板引用"""
        self.marker_list_panel = panel

    def set_main_window(self, window):
        """设置主窗口引用"""
        self.main_window = window

    def _value_to_pixel(self, val):
        """将时间值转换为像素位置"""
        if self.duration_ms <= 0:
            return 0
        return int((val / self.duration_ms) * self.width())

    def _pixel_to_value(self, x):
        """将像素位置转换为时间值"""
        if self.width() <= 0:
            return 0
        ratio = x / self.width()
        return int(max(0, min(1, ratio)) * self.duration_ms)

    def _find_marker_at(self, x):
        """检测鼠标位置是否在标记上，返回 (marker, index) 或 (None, None)"""
        if self.duration_ms <= 0:
            return None, None

        for i, marker in enumerate(self.markers):
            if marker.get('type') == 0: # 点标记
                marker_x = self._value_to_pixel(marker["time"])
                if abs(marker_x - x) < self.snap_threshold:
                    return marker, i
            else: # 范围标记
                x1 = self._value_to_pixel(marker["start"])
                x2 = self._value_to_pixel(marker["end"])
                if x1 <= x <= x2:
                    return marker, i

        return None, None

    def _find_markers_at(self, x):
        """检测鼠标位置是否在标记上，返回所有重叠的标记列表"""
        if self.duration_ms <= 0:
            return []

        overlapping_markers = []
        for marker in self.markers:
            if marker.get('type') == 0: # 点标记
                marker_x = self._value_to_pixel(marker["time"])
                if abs(marker_x - x) < self.snap_threshold:
                    overlapping_markers.append(marker)                
            else: # 范围标记
                x1 = self._value_to_pixel(marker["start"])
                x2 = self._value_to_pixel(marker["end"])
                if x1 <= x <= x2:
                    overlapping_markers.append(marker)

        return overlapping_markers

    def _open_marker_edit_dialog(self, marker_data=None):
        """打开标记编辑对话框"""
        # 获取预设列表
        presets = self.DictManage.get_all_marker_presets()

        dialog = MarkerEditDialog(
            marker_data=marker_data,
            presets=presets,
            max_duration_ms=self.duration_ms,
            parent=self
        )
        if dialog.exec_() == MarkerEditDialog.Accepted:
            return dialog.get_data()
        return None

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件 - 显示标记信息"""
        # 获取鼠标位置上的所有重叠标记
        overlapping_markers = self._find_markers_at(event.x())

        if overlapping_markers:
            # 构建显示文本，显示所有重叠标记的信息
            display_lines = []
            for m in overlapping_markers:
                if m.get('type') == 0:  # 点标记
                    time_str = format_time(m['time'])
                    display_lines.append(f"{m.get('label', '')} - {time_str}")
                else:  # 范围标记
                    start_str = format_time(m['start'])
                    end_str = format_time(m['end'])
                    display_lines.append(f"{m.get('label', '')} - {start_str}~{end_str}")

            display_text = "\n".join(display_lines)

            self.floating_label.setText(display_text)
            self.floating_label.adjustSize()
            glob_pos = self.mapToGlobal(QPoint(event.x() - self.floating_label.width()//2, -45))
            self.floating_label.move(glob_pos)
            self.floating_label.show()
        else:
            # 如果没有悬停在标记上，隐藏提示
            self.floating_label.hide()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件"""
        super().mouseReleaseEvent(event)

    def _reload_markers(self):
        """从数据库重新加载标记"""
        if not self.audio_file_path:
            return

        normalized_path = self.audio_file_path
        self.markers = self.DictManage.get_audio_markers(normalized_path)
        self.update()

    def leaveEvent(self, event):
        """鼠标离开事件"""
        self.floating_label.hide()
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单事件 - 只在标记上右键时显示"""
        click_x = event.x()
        marker, marker_idx = self._find_marker_at(click_x)

        if marker:
            # 在标记上右键：显示编辑和删除选项
            menu = QMenu(self)
            edit_action = menu.addAction("📝 编辑标记")
            delete_action = menu.addAction("🗑️ 删除标记")

            action = menu.exec_(event.globalPos())

            if action == edit_action:
                # 调用主窗口的统一编辑方法
                if self.main_window:
                    self.main_window.edit_marker(marker)
            elif action == delete_action:
                self._delete_marker(marker)

    def _delete_marker(self, marker):
        """删除标记"""
        if not self.audio_file_path:
            return

        normalized_path = self.audio_file_path

        # 从数据库删除
        self.DictManage.delete_audio_marker(normalized_path, marker['id'])

        # 重新加载标记
        self._reload_markers()

        # 刷新标记列表面板
        if self.marker_list_panel:
            self.marker_list_panel.load_markers()

    def mousePressEvent(self, event: QMouseEvent):
        """点击标记跳转到对应位置"""
        if event.button() == Qt.LeftButton:
            click_x = event.x()
            overlapping_markers = self._find_markers_at(click_x)

            if overlapping_markers:
                # 获取鼠标点击位置对应的时间
                click_time = self._pixel_to_value(click_x)

                # 如果有多个重叠标记，跳转到开始时间距离鼠标点击位置最近的那个
                closest_marker = None
                min_distance = float('inf')

                for marker in overlapping_markers:
                    # 获取标记的开始时间
                    if marker.get('type') == 0:  # 点标记
                        marker_start = marker['time']
                    else:  # 范围标记
                        marker_start = marker['start']

                    # 计算距离鼠标点击位置的距离
                    distance = abs(marker_start - click_time)

                    if distance < min_distance:
                        min_distance = distance
                        closest_marker = marker

                # 跳转到最近的标记
                if closest_marker:
                    if closest_marker.get('type') == 0:  # 点标记
                        target_val = closest_marker['time']
                    else:  # 范围标记，跳转到起点
                        target_val = closest_marker['start']

                    # 发出跳转信号
                    self.markerJumped.emit(target_val)

        super().mousePressEvent(event)

    def paintEvent(self, event):
        """绘制标记显示区域"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制背景
        painter.fillRect(self.rect(), QColor("#f5f5f5"))

        # 绘制边框
        painter.setPen(QColor("#ddd"))
        painter.drawRoundedRect(0, 0, self.width() - 1, self.height() - 1, 3, 3)

        if not self.duration_ms or not self.markers:
            painter.end()
            return

        # 绘制标记
        for marker in self.markers:
            color = QColor(marker.get('color', '#3498db'))
            if marker.get('type') == 0: # 点标记
                x = self._value_to_pixel(marker['time'])
                painter.setBrush(color)
                painter.setPen(Qt.NoPen)
                painter.drawRect(x - 2, 4, 4, self.height() - 8)
            else:  # 范围标记
                x1 = self._value_to_pixel(marker['start'])
                x2 = self._value_to_pixel(marker['end'])
                rect_color = QColor(color)
                rect_color.setAlpha(100)
                painter.setBrush(rect_color)
                painter.setPen(color)
                painter.drawRect(x1, 8, x2 - x1, self.height() - 16)

        painter.end()