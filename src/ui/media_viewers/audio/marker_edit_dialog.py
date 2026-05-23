from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from src.ui.components.style_utils import apply_color_preview_button_style
from src.ui.components.time_input import TimeInput


class MarkerEditDialog(QDialog):
    def __init__(self, marker_data=None, presets=None, max_duration_ms=None, parent=None):
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
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        if self.presets:
            preset_group = QGroupBox("预设类型")
            preset_layout = QHBoxLayout()
            preset_layout.setSpacing(10)
            self.preset_button_group = QButtonGroup(self)
            self.preset_buttons = []

            for preset_id, name, color, _order_index in self.presets:
                button = QPushButton(name)
                button.setCheckable(True)
                button.setMinimumHeight(35)
                button.setStyleSheet(f"""
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
                """)
                button.clicked.connect(
                    lambda checked, preset_color=color, preset_id=preset_id: self.on_preset_selected(
                        preset_color,
                        preset_id,
                    )
                )
                preset_layout.addWidget(button)
                self.preset_button_group.addButton(button)
                self.preset_buttons.append(button)

                if self.selected_preset_id == preset_id:
                    button.setChecked(True)

            preset_group.setLayout(preset_layout)
            layout.addWidget(preset_group)

        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("颜色:"))

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(60, 30)
        self.color_btn.clicked.connect(self.choose_color)
        color_layout.addWidget(self.color_btn)

        self.color_label = QLabel(self.current_color)
        self.color_label.setStyleSheet("color: #555; font-family: monospace;")
        color_layout.addWidget(self.color_label)
        color_layout.addStretch()
        layout.addLayout(color_layout)
        self._update_color_button()

        layout.addWidget(QLabel("备注内容:"))
        self.text_edit = QTextEdit()
        self.text_edit.setMaximumHeight(100)
        self.text_edit.setPlaceholderText("输入标记备注...")
        self.text_edit.setPlainText(self.marker_data.get('label', ''))
        layout.addWidget(self.text_edit)

        time_group = QGroupBox("时间设置")
        time_layout = QVBoxLayout()
        time_layout.setSpacing(10)

        time_input_layout = QHBoxLayout()
        time_input_layout.setSpacing(8)
        start_label = QLabel("开始:")
        start_label.setFixedWidth(40)
        time_input_layout.addWidget(start_label)

        self.start_time_input = TimeInput(max_duration_ms=self.max_duration_ms)
        time_input_layout.addWidget(self.start_time_input)

        separator = QLabel("-")
        separator.setAlignment(Qt.AlignCenter)
        separator.setStyleSheet("color: #7f8c8d; font-weight: bold; font-size: 14px;")
        time_input_layout.addWidget(separator)

        end_label = QLabel("结束:")
        end_label.setFixedWidth(40)
        time_input_layout.addWidget(end_label)

        self.end_time_input = TimeInput(max_duration_ms=self.max_duration_ms)
        time_input_layout.addWidget(self.end_time_input)
        time_input_layout.addStretch()
        time_layout.addLayout(time_input_layout)

        tip_label = QLabel("只填写开始时间会保存为点标记，填写开始和结束时间会保存为区间标记。")
        tip_label.setWordWrap(True)
        tip_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        time_layout.addWidget(tip_label)
        time_group.setLayout(time_layout)
        layout.addWidget(time_group)

        if self.marker_data.get('type') == 0:
            self.start_time_input.set_from_milliseconds(self.marker_data.get('time', 0))
        elif self.marker_data:
            self.start_time_input.set_from_milliseconds(self.marker_data.get('start', 0))
            self.end_time_input.set_from_milliseconds(self.marker_data.get('end', 0))

        layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumWidth(80)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

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
        button_layout.addWidget(save_btn)
        layout.addLayout(button_layout)

    def _update_color_button(self):
        apply_color_preview_button_style(self.color_btn, self.current_color)
        self.color_label.setText(self.current_color)

    def on_preset_selected(self, color, preset_id):
        self.current_color = color
        self.selected_preset_id = preset_id
        self._update_color_button()

        for row_preset_id, name, _preset_color, _order_index in self.presets:
            if row_preset_id == preset_id:
                self.text_edit.setPlainText(name)
                break

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.current_color), self, "选择标记颜色")
        if color.isValid():
            self.current_color = color.name()
            self._update_color_button()
            if hasattr(self, 'preset_button_group'):
                checked_button = self.preset_button_group.checkedButton()
                if checked_button:
                    checked_button.setChecked(False)
            self.selected_preset_id = None

    def accept(self):
        start_ms = self.start_time_input.get_milliseconds()
        end_ms = self.end_time_input.get_milliseconds()

        if start_ms is None and end_ms is None:
            QMessageBox.warning(self, "错误", "请至少输入一个时间")
            return

        if end_ms is not None:
            if start_ms is None:
                start_ms = 0
            if end_ms < start_ms:
                QMessageBox.warning(self, "错误", "结束时间不能小于开始时间")
                return

        super().accept()

    def get_data(self):
        start_ms = self.start_time_input.get_milliseconds()
        end_ms = self.end_time_input.get_milliseconds()
        label = self.text_edit.toPlainText().strip()

        if end_ms is None:
            return {
                'type': 0,
                'time': start_ms if start_ms is not None else 0,
                'label': label,
                'color': self.current_color,
                'preset_id': self.selected_preset_id,
            }

        if start_ms is None:
            start_ms = 0

        return {
            'type': 1,
            'start': start_ms,
            'end': end_ms,
            'label': label,
            'color': self.current_color,
            'preset_id': self.selected_preset_id,
        }
