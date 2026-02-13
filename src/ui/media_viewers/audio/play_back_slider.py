from PyQt5.QtWidgets import QSlider, QLabel, QStyle, QStyleOptionSlider, QMenu
from PyQt5.QtCore import Qt, QPoint, QTime
from PyQt5.QtGui import QMouseEvent

def format_time(ms):
    '''格式化毫秒为 00:00 格式'''
    time = QTime(0, 0).addMSecs(ms)
    return time.toString("mm:ss")

class PlaybackSlider(QSlider):
    """播放进度条 - 负责播放位置控制和时间设置"""

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setMouseTracking(True)

        # 快速标记创建器引用（用于设置时间）
        self.quick_marker_creator = None

        # 顶层悬浮标签 (显示时间)
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
        """设置快速标记创建器引用"""
        self.quick_marker_creator = creator

    def _get_track_info(self):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        rect = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
        margin = 12
        return rect.left() + margin, rect.width() - margin * 2

    def _pixel_to_value(self, x):
        offset, width = self._get_track_info()
        if width <= 0: return 0
        ratio = (x - offset) / width
        return int(max(0, min(1, ratio)) * self.maximum())

    def mouseMoveEvent(self, event: QMouseEvent):
        """显示时间预览"""
        curr_val = self._pixel_to_value(event.x())
        time_str = format_time(curr_val)
        display_text = f"🕒 {time_str}"

        self.floating_label.setText(display_text)
        self.floating_label.adjustSize()
        glob_pos = self.mapToGlobal(QPoint(event.x() - self.floating_label.width()//2, -45))
        self.floating_label.move(glob_pos)
        self.floating_label.show()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.floating_label.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """点击进度条跳转到对应位置"""
        if event.button() == Qt.LeftButton:
            click_x = event.x()
            target_val = self._pixel_to_value(click_x)

            self.setValue(target_val)
            self.sliderMoved.emit(target_val)

        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单：设置开始/结束时间"""
        if not self.quick_marker_creator:
            return

        click_x = event.x()
        menu = QMenu(self)

        set_start_time_action = menu.addAction("⏱️ 设置为开始时间")
        set_end_time_action = menu.addAction("⏱️ 设置为结束时间")

        action = menu.exec_(event.globalPos())

        if action == set_start_time_action:
            time_pos = self._pixel_to_value(click_x)
            self.quick_marker_creator.start_time_input.set_from_milliseconds(time_pos)
        elif action == set_end_time_action:
            time_pos = self._pixel_to_value(click_x)
            self.quick_marker_creator.end_time_input.set_from_milliseconds(time_pos)