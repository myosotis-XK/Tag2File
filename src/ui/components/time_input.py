"""
TimeInput 组件 - 时间输入组件（HH:MM:SS格式）

功能特性：
- 外观上是一个完整的输入框，内部由3个独立的数字输入框组成
- 支持智能自动跳转（输入满2位或输入6-9时自动跳到下一个框）
- 支持键盘方向键导航
- 整体焦点状态控制（任意内部输入框获得焦点时，整个组件边框变蓝）
- 提供获取毫秒值和清空的方法
"""

from PyQt5.QtWidgets import QWidget, QLineEdit, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator, QPainter, QPen, QColor, QPalette


class TimeDigitInput(QLineEdit):
    """时间数字输入框 - 自定义QLineEdit子类"""

    def __init__(self, min_value, max_value, parent_widget, prev_input=None, next_input=None):
        """
        初始化时间数字输入框

        Args:
            min_value: 最小值
            max_value: 最大值
            parent_widget: 父组件（TimeInput实例）
            prev_input: 前一个输入框
            next_input: 后一个输入框
        """
        super().__init__()
        self.min_value = min_value
        self.max_value = max_value
        self.parent_widget = parent_widget
        self.prev_input = prev_input
        self.next_input = next_input

        # 设置验证器
        self.setValidator(QIntValidator(min_value, max_value))

        # 设置样式
        self.setFixedWidth(20)
        self.setAlignment(Qt.AlignCenter)
        self.setPlaceholderText("00")
        self.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
            }
        """)

        # 设置最大长度为2位
        self.setMaxLength(2)

    def keyPressEvent(self, event):
        """处理键盘事件"""
        key = event.key()
        text = self.text()
        cursor_pos = self.cursorPosition()

        # 处理左方向键导航
        if key == Qt.Key_Left:
            if cursor_pos == 0 and self.prev_input:
                self.prev_input.setFocus()
                self.prev_input.setCursorPosition(len(self.prev_input.text()))
                return

        # 处理右方向键导航
        elif key == Qt.Key_Right:
            if cursor_pos == len(text) and self.next_input:
                self.next_input.setFocus()
                self.next_input.setCursorPosition(0)
                return

        # 处理数字输入
        elif event.text().isdigit():
            # 如果已经有2位数字，且没有选中文本，则不允许继续输入
            if len(text) >= 2 and not self.hasSelectedText():
                return

            # 调用父类方法进行输入
            super().keyPressEvent(event)

            # 输入后检查是否需要自动跳转
            new_text = self.text()
            self._check_auto_jump(new_text)
            return

        # 其他按键使用默认处理
        super().keyPressEvent(event)

    def _check_auto_jump(self, text):
        """检查是否需要自动跳转到下一个输入框"""
        if not self.next_input:
            return

        # 如果输入满2位，自动跳转
        if len(text) == 2:
            self.next_input.setFocus()
            self.next_input.selectAll()
            return

        # 对于分钟和秒输入框（0-59范围），如果第一位输入6-9，立即跳转
        if self.max_value == 59 and len(text) == 1:
            first_digit = int(text)
            if first_digit >= 6:
                self.next_input.setFocus()
                self.next_input.selectAll()

    def focusInEvent(self, event):
        """获得焦点时通知父组件更新边框"""
        super().focusInEvent(event)
        self.parent_widget.update_border_style()

    def focusOutEvent(self, event):
        """失去焦点时通知父组件更新边框并验证输入"""
        super().focusOutEvent(event)
        self.parent_widget.update_border_style()

        # 失焦时验证并调整输入值
        self.parent_widget.validate_and_adjust()


class TimeInput(QWidget):
    """时间输入组件 - 主组件类"""

    def __init__(self, parent=None, max_duration_ms=None):
        """
        初始化TimeInput组件

        Args:
            parent: 父组件
            max_duration_ms: 最大允许时长（毫秒），None表示不限制
        """
        super().__init__(parent)

        # 存储最大时长限制
        self.max_duration_ms = max_duration_ms

        # 存储边框颜色状态
        self.border_color = "#cccccc"  # 默认灰色

        # 设置白色背景（使用QPalette方式）
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(255, 255, 255))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        # 创建布局
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # 创建三个输入框
        self.hour_input = TimeDigitInput(0, 99, self)
        self.minute_input = TimeDigitInput(0, 59, self)
        self.second_input = TimeDigitInput(0, 59, self)

        # 设置相邻输入框引用
        self.hour_input.next_input = self.minute_input
        self.minute_input.prev_input = self.hour_input
        self.minute_input.next_input = self.second_input
        self.second_input.prev_input = self.minute_input

        # 创建冒号分隔符
        colon1 = QLabel(":")
        colon2 = QLabel(":")
        colon1.setStyleSheet("color: #888888; background: transparent;")
        colon2.setStyleSheet("color: #888888; background: transparent;")

        # 添加组件到布局
        layout.addWidget(self.hour_input)
        layout.addWidget(colon1)
        layout.addWidget(self.minute_input)
        layout.addWidget(colon2)
        layout.addWidget(self.second_input)
        layout.addStretch()

        self.setLayout(layout)

        # 设置整体样式
        self.setFixedSize(90, 30)
        self.update_border_style()

    def update_border_style(self):
        """更新整体边框样式（根据焦点状态）"""
        # 检查是否有任意输入框获得焦点
        has_focus = (
            self.hour_input.hasFocus() or
            self.minute_input.hasFocus() or
            self.second_input.hasFocus()
        )

        # 根据焦点状态设置边框颜色
        if has_focus:
            self.border_color = "#0078d4"  # 蓝色
        else:
            self.border_color = "#cccccc"  # 灰色

        # 触发重绘
        self.update()

    def paintEvent(self, event):
        """自定义绘制事件 - 绘制白色背景和边框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 抗锯齿

        # 绘制白色背景
        painter.fillRect(self.rect(), QColor("white"))

        # 绘制边框
        pen = QPen(QColor(self.border_color))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # 绘制圆角矩形边框
        painter.drawRoundedRect(0, 0, self.width() - 1, self.height() - 1, 3, 3)

    def get_milliseconds(self):
        """
        获取输入的时间值（转换为毫秒）

        Returns:
            int: 时间的毫秒值，如果所有输入框都为空则返回None
        """
        hour_text = self.hour_input.text()
        minute_text = self.minute_input.text()
        second_text = self.second_input.text()

        # 如果所有输入框都为空，返回None
        if not hour_text and not minute_text and not second_text:
            return None

        # 空值按0处理
        hours = int(hour_text) if hour_text else 0
        minutes = int(minute_text) if minute_text else 0
        seconds = int(second_text) if second_text else 0

        # 计算总毫秒数
        total_seconds = hours * 3600 + minutes * 60 + seconds
        return total_seconds * 1000

    def set_max_duration(self, max_duration_ms):
        """
        设置最大允许时长

        Args:
            max_duration_ms: 最大时长（毫秒），None表示不限制
        """
        self.max_duration_ms = max_duration_ms

    def validate_and_adjust(self):
        """
        验证并调整输入值，使其不超过最大时长
        当输入框失去焦点时调用
        """
        # 如果没有设置最大时长限制，不处理
        if self.max_duration_ms is None:
            return

        # 获取当前输入的时长
        current_ms = self.get_milliseconds()

        # 如果为空，不处理
        if current_ms is None:
            return

        # 如果超过最大时长，自动调整为最大值
        if current_ms > self.max_duration_ms:
            max_hours = self.max_duration_ms // 3600000
            max_minutes = (self.max_duration_ms % 3600000) // 60000
            max_seconds = (self.max_duration_ms % 60000) // 1000

            # 设置为最大值
            self.hour_input.setText(str(max_hours) if max_hours > 0 else "")
            self.minute_input.setText(f"{max_minutes:02d}" if max_hours > 0 or max_minutes > 0 else "")
            self.second_input.setText(f"{max_seconds:02d}")

    def clear(self):
        """清空所有输入框"""
        self.hour_input.clear()
        self.minute_input.clear()
        self.second_input.clear()

    def set_from_milliseconds(self, milliseconds):
        """
        从毫秒值设置时间输入框的值

        Args:
            milliseconds: 毫秒值
        """
        if milliseconds is None:
            self.clear()
            return

        # 计算小时、分钟、秒
        total_seconds = milliseconds // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        # 设置各个输入框的值
        if hours > 0:
            self.hour_input.setText(str(hours))
            self.minute_input.setText(f"{minutes:02d}")
            self.second_input.setText(f"{seconds:02d}")
        elif minutes > 0:
            self.hour_input.setText("")
            self.minute_input.setText(str(minutes))
            self.second_input.setText(f"{seconds:02d}")
        else:
            self.hour_input.setText("")
            self.minute_input.setText("")
            self.second_input.setText(str(seconds))
