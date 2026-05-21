from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QColorDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.ui.components.preset_selector_dialog import PresetSelectorDialog
from src.ui.components.time_input import TimeInput

from .marker_store import MarkerStore


class QuickMarkerCreator(QWidget):
    marker_create_requested = pyqtSignal(dict)

    def __init__(self, audio_file_path=None, parent=None):
        super().__init__(parent)
        self.audio_file_path = audio_file_path
        self.current_color = "#3498db"
        self.selected_preset_id = None
        self.marker_store = MarkerStore()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(5)
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f6fa;
                border-radius: 5px;
            }
        """)

        time_layout = QHBoxLayout()
        time_layout.setSpacing(8)

        self.start_time_input = TimeInput()
        time_layout.addWidget(self.start_time_input)

        separator_label = QLabel("-")
        separator_label.setAlignment(Qt.AlignCenter)
        separator_label.setStyleSheet("""
            color: #7f8c8d;
            font-weight: bold;
            font-size: 14px;
            background-color: transparent;
        """)
        time_layout.addWidget(separator_label)

        self.end_time_input = TimeInput()
        time_layout.addWidget(self.end_time_input)
        time_layout.addStretch()

        self.create_btn = QPushButton("创建")
        self.create_btn.setFixedWidth(50)
        self.create_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        self.create_btn.clicked.connect(self.validate_and_create)
        time_layout.addWidget(self.create_btn)
        main_layout.addLayout(time_layout)

        control_layout = QHBoxLayout()
        control_layout.setSpacing(5)

        self.preset_btn = QPushButton("预设")
        self.preset_btn.setFixedWidth(35)
        self.preset_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:pressed {
                background-color: #6c7a7b;
            }
        """)
        self.preset_btn.clicked.connect(self.show_preset_menu)
        control_layout.addWidget(self.preset_btn)

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(24, 24)
        self.color_btn.clicked.connect(self.choose_color)
        control_layout.addWidget(self.color_btn)
        self.update_color_button()

        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("标记备注")
        self.label_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                padding: 4px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        control_layout.addWidget(self.label_input)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setFixedWidth(50)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:pressed {
                background-color: #6c7a7b;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_all)
        control_layout.addWidget(self.clear_btn)
        main_layout.addLayout(control_layout)

    def update_color_button(self):
        self.color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.current_color};
                border: 1px solid #7f8c8d;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                border: 2px solid #2c3e50;
            }}
        """)

    def set_audio_file_path(self, path, duration_ms=None):
        self.audio_file_path = path
        if duration_ms is not None:
            self.start_time_input.set_max_duration(duration_ms)
            self.end_time_input.set_max_duration(duration_ms)

    def show_preset_menu(self):
        presets = self.marker_store.get_preset_rows()
        if not presets:
            QMessageBox.information(self, "提示", "暂无预设，请先在预设管理器中创建预设")
            return

        dialog = PresetSelectorDialog(
            presets=presets,
            current_preset_id=self.selected_preset_id,
            parent=self,
        )
        dialog.move(self.preset_btn.mapToGlobal(self.preset_btn.rect().bottomLeft()))

        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_selected_data()
            if data:
                self.on_preset_selected(data['id'], data['color'], data['name'])

    def on_preset_selected(self, preset_id, color, name):
        self.current_color = color
        self.selected_preset_id = preset_id
        self.update_color_button()
        self.label_input.setText(name)

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.current_color), self, "选择标记颜色")
        if color.isValid():
            self.current_color = color.name()
            self.selected_preset_id = None
            self.update_color_button()

    def clear_all(self):
        self.start_time_input.clear()
        self.end_time_input.clear()
        self.label_input.clear()
        self.current_color = "#3498db"
        self.selected_preset_id = None
        self.update_color_button()

    def validate_and_create(self):
        if not self.audio_file_path:
            QMessageBox.warning(self, "错误", "未加载音频文件")
            return

        start_ms = self.start_time_input.get_milliseconds()
        end_ms = self.end_time_input.get_milliseconds()
        if start_ms is None and end_ms is None:
            QMessageBox.warning(self, "错误", "请至少输入一个时间")
            return

        label = self.label_input.text().strip() or "未命名标记"

        if end_ms is None:
            marker_data = {
                'type': 0,
                'time': start_ms if start_ms is not None else end_ms,
                'label': label,
                'color': self.current_color,
                'preset_id': self.selected_preset_id,
            }
        else:
            if start_ms is None:
                start_ms = 0
            if end_ms < start_ms:
                QMessageBox.warning(self, "错误", "结束时间不能小于开始时间")
                return
            marker_data = {
                'type': 1,
                'start': start_ms,
                'end': end_ms,
                'label': label,
                'color': self.current_color,
                'preset_id': self.selected_preset_id,
            }

        self.marker_create_requested.emit(marker_data)
