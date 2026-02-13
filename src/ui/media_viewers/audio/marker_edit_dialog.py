from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QTextEdit, QGroupBox, QColorDialog, QButtonGroup, QMessageBox)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
from src.ui.components.time_input import TimeInput


def format_time(ms):
    """格式化毫秒为 mm:ss 格式"""
    from PyQt5.QtCore import QTime
    time = QTime(0, 0).addMSecs(ms)
    return time.toString("mm:ss")


class MarkerEditDialog(QDialog):
    """标记编辑对话框"""

    def __init__(self, marker_data=None, presets=None, max_duration_ms=None, parent=None):
        """
        初始化标记编辑对话框

        :param marker_data: 现有标记数据字典 {'type', 'time'/'start'/'end', 'label', 'color', 'preset_id'}
                           或 None（新建标记）
        :param presets: 预设列表 [(id, name, color, order_index), ...]
        :param max_duration_ms: 音频最大时长（毫秒），用于时间输入验证
        :param parent: 父窗口
        """
        super().__init__(parent)
        self.marker_data = marker_data or {}
        self.presets = presets or []
        self.current_color = self.marker_data.get('color', '#3498db')
        self.selected_preset_id = self.marker_data.get('preset_id')
        self.max_duration_ms = max_duration_ms

        self.setWindowTitle("编辑标记" if marker_data else "创建标记")
        self.resize(450, 450)

        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 1. 预设类型选择区
        if self.presets:
            preset_group = QGroupBox("预设类型")
            preset_layout = QHBoxLayout()
            preset_layout.setSpacing(10)

            self.preset_button_group = QButtonGroup(self)
            self.preset_buttons = []

            for preset_id, name, color, order_index in self.presets:
                btn = QPushButton(name)
                btn.setCheckable(True)
                btn.setMinimumHeight(35)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {color};
                        color: white;
                        border: 2px solid transparent;
                        border-radius: 5px;
                        font-weight: bold;
                        padding: 5px 10px;
                    }}
                    QPushButton:checked {{
                        border: 2px solid #2c3e50;
                    }}
                    QPushButton:hover {{
                        opacity: 0.8;
                    }}
                """)

                # 保存预设信息到按钮
                btn.setProperty('preset_id', preset_id)
                btn.setProperty('preset_color', color)

                # 连接点击事件
                btn.clicked.connect(lambda checked, c=color, pid=preset_id: self.on_preset_selected(c, pid))

                preset_layout.addWidget(btn)
                self.preset_button_group.addButton(btn)
                self.preset_buttons.append(btn)

                # 如果是当前选中的预设，设为选中状态
                if self.selected_preset_id == preset_id:
                    btn.setChecked(True)

            preset_group.setLayout(preset_layout)
            layout.addWidget(preset_group)

        # 2. 颜色选择器
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("颜色:"))

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(60, 30)
        self.color_btn.setStyleSheet(f"background-color: {self.current_color}; border: 1px solid #555;")
        self.color_btn.clicked.connect(self.choose_color)
        color_layout.addWidget(self.color_btn)

        self.color_label = QLabel(self.current_color)
        self.color_label.setStyleSheet("color: #555; font-family: monospace;")
        color_layout.addWidget(self.color_label)

        color_layout.addStretch()
        layout.addLayout(color_layout)

        # 3. 注释文本输入
        layout.addWidget(QLabel("注释内容:"))
        self.text_edit = QTextEdit()
        self.text_edit.setMaximumHeight(100)
        self.text_edit.setPlaceholderText("输入标记注释...")

        if self.marker_data:
            self.text_edit.setPlainText(self.marker_data.get('label', ''))

        layout.addWidget(self.text_edit)

        # 4. 时间编辑区域
        time_group = QGroupBox("时间设置")
        time_layout = QVBoxLayout()
        time_layout.setSpacing(10)

        # 时间输入行
        time_input_layout = QHBoxLayout()
        time_input_layout.setSpacing(8)

        # 开始时间标签和输入
        start_label = QLabel("开始:")
        start_label.setFixedWidth(40)
        time_input_layout.addWidget(start_label)

        self.start_time_input = TimeInput(max_duration_ms=self.max_duration_ms)
        time_input_layout.addWidget(self.start_time_input)

        # 分隔符
        separator = QLabel("-")
        separator.setStyleSheet("color: #7f8c8d; font-weight: bold; font-size: 14px;")
        separator.setAlignment(Qt.AlignCenter)
        time_input_layout.addWidget(separator)

        # 结束时间标签和输入
        end_label = QLabel("结束:")
        end_label.setFixedWidth(40)
        time_input_layout.addWidget(end_label)

        self.end_time_input = TimeInput(max_duration_ms=self.max_duration_ms)
        time_input_layout.addWidget(self.end_time_input)

        time_input_layout.addStretch()

        time_layout.addLayout(time_input_layout)

        # 提示文本
        tip_label = QLabel("💡 提示: 只填开始时间为点标记，填写开始和结束时间为范围标记")
        tip_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        tip_label.setWordWrap(True)
        time_layout.addWidget(tip_label)

        time_group.setLayout(time_layout)
        layout.addWidget(time_group)

        # 如果是编辑模式，预填充时间数据
        if self.marker_data:
            marker_type = self.marker_data.get('type', 0)
            if marker_type == 0:  # 点标记
                time_ms = self.marker_data.get('time', 0)
                self.start_time_input.set_from_milliseconds(time_ms)
            else:  # 范围标记
                start_ms = self.marker_data.get('start', 0)
                end_ms = self.marker_data.get('end', 0)
                self.start_time_input.set_from_milliseconds(start_ms)
                self.end_time_input.set_from_milliseconds(end_ms)

        # 5. 按钮区
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumWidth(80)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setMinimumWidth(80)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def on_preset_selected(self, color, preset_id):
        """预设类型被选中时的回调"""
        self.current_color = color
        self.selected_preset_id = preset_id
        self.color_btn.setStyleSheet(f"background-color: {color}; border: 1px solid #555;")
        self.color_label.setText(color)

        # 自动填充注释：查找对应预设的名称
        for p_id, name, p_color, order_index in self.presets:
            if p_id == preset_id:
                # 每次点击预设时都自动填充注释
                self.text_edit.setPlainText(name)
                break

    def choose_color(self):
        """打开颜色选择对话框"""
        initial_color = QColor(self.current_color)
        color = QColorDialog.getColor(initial_color, self, "选择标记颜色")

        if color.isValid():
            self.current_color = color.name()
            self.color_btn.setStyleSheet(f"background-color: {self.current_color}; border: 1px solid #555;")
            self.color_label.setText(self.current_color)

            # 取消预设选择
            if hasattr(self, 'preset_button_group'):
                checked_btn = self.preset_button_group.checkedButton()
                if checked_btn:
                    checked_btn.setChecked(False)
            self.selected_preset_id = None

    def accept(self):
        """保存前验证时间输入"""
        # 获取时间值
        start_ms = self.start_time_input.get_milliseconds()
        end_ms = self.end_time_input.get_milliseconds()

        # 至少需要一个时间
        if start_ms is None and end_ms is None:
            QMessageBox.warning(self, "错误", "请至少输入一个时间")
            return

        # 如果是范围标记，验证时间顺序
        if end_ms is not None:
            if start_ms is None:
                start_ms = 0
            if end_ms < start_ms:
                QMessageBox.warning(self, "错误", "结束时间不能小于开始时间")
                return

        # 验证通过，调用父类的accept
        super().accept()

    def get_data(self):
        """
        获取用户输入的数据

        :return: {'type': int, 'time'/'start'/'end': int, 'label': str, 'color': str, 'preset_id': int or None}
        """
        # 获取时间
        start_ms = self.start_time_input.get_milliseconds()
        end_ms = self.end_time_input.get_milliseconds()

        # 获取注释
        label = self.text_edit.toPlainText().strip()
        if not label:
            label = "未命名标记"

        # 判断标记类型
        if end_ms is None:
            # 点标记
            return {
                'type': 0,
                'time': start_ms if start_ms is not None else 0,
                'label': label,
                'color': self.current_color,
                'preset_id': self.selected_preset_id
            }
        else:
            # 范围标记
            if start_ms is None:
                start_ms = 0
            return {
                'type': 1,
                'start': start_ms,
                'end': end_ms,
                'label': label,
                'color': self.current_color,
                'preset_id': self.selected_preset_id
            }