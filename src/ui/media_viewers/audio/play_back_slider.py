from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QMenu, QLabel, QSlider, QStyle, QStyleOptionSlider
from src.ui.components.style_utils import create_context_menu

from .audio_utils import format_time


class PlaybackSlider(QSlider):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setMouseTracking(True)
        self.quick_marker_creator = None

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

    def set_quick_marker_creator(self, creator):
        self.quick_marker_creator = creator

    def _get_track_info(self):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        groove_rect = self.style().subControlRect(
            QStyle.CC_Slider,
            option,
            QStyle.SC_SliderGroove,
            self,
        )
        margin = 12
        return groove_rect.left() + margin, groove_rect.width() - margin * 2

    def _pixel_to_value(self, x_pos):
        offset, width = self._get_track_info()
        if width <= 0:
            return 0
        ratio = (x_pos - offset) / width
        return int(max(0, min(1, ratio)) * self.maximum())

    def mouseMoveEvent(self, event: QMouseEvent):
        current_value = self._pixel_to_value(event.x())
        self.floating_label.setText(f"时间 {format_time(current_value)}")
        self.floating_label.adjustSize()
        global_pos = self.mapToGlobal(QPoint(event.x() - self.floating_label.width() // 2, -45))
        self.floating_label.move(global_pos)
        self.floating_label.show()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.floating_label.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            target_value = self._pixel_to_value(event.x())
            self.setValue(target_value)
            self.sliderMoved.emit(target_value)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        if not self.quick_marker_creator:
            return

        menu = create_context_menu(self)
        set_start_action = menu.addAction("设为开始时间")
        set_end_action = menu.addAction("设为结束时间")
        action = menu.exec_(event.globalPos())
        time_pos = self._pixel_to_value(event.x())

        if action == set_start_action:
            self.quick_marker_creator.start_time_input.set_from_milliseconds(time_pos)
        elif action == set_end_action:
            self.quick_marker_creator.end_time_input.set_from_milliseconds(time_pos)
