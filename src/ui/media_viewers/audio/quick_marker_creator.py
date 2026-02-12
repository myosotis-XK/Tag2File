from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLineEdit,
                             QPushButton, QColorDialog, QMessageBox, QLabel, QDialog)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor
from src.ui.components.time_input import TimeInput
from src.ui.components.preset_selector_dialog import PresetSelectorDialog


class QuickMarkerCreator(QWidget):
    """快速创建标记输入区域"""

    marker_created = pyqtSignal()  # 标记创建成功后发出

    def __init__(self, audio_file_path=None, parent=None):
        super().__init__(parent)
        self.audio_file_path = audio_file_path
        self.current_color = "#3498db"  # 默认颜色
        self.selected_preset_id = None

        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(5)

        # 设置整体样式
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f6fa;
                border-radius: 5px;
            }
        """)

        # 第一行：时间输入和创建按钮
        time_layout = QHBoxLayout()
        time_layout.setSpacing(8)

        # 开始时间（时:分:秒）
        self.start_time_input = TimeInput()
        time_layout.addWidget(self.start_time_input)

        # 分隔符 "-"
        separator_label = QLabel("-")
        separator_label.setStyleSheet("""
            color: #7f8c8d;
            font-weight: bold;
            font-size: 14px;
            background-color: transparent;
        """)
        separator_label.setAlignment(Qt.AlignCenter)
        time_layout.addWidget(separator_label)

        # 结束时间（时:分:秒）
        self.end_time_input = TimeInput()
        time_layout.addWidget(self.end_time_input)

        time_layout.addStretch()

        # 创建按钮
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

        # 第二行：预设、颜色、注释和清空
        control_layout = QHBoxLayout()
        control_layout.setSpacing(5)

        # 预设按钮
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

        # 颜色选择按钮
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(24, 24)
        self.update_color_button()
        self.color_btn.clicked.connect(self.choose_color)
        control_layout.addWidget(self.color_btn)

        # 注释输入框
        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("标记注释")
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

        # 清空按钮
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
        """更新颜色按钮的显示"""
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
        """
        设置音频文件路径和时长

        Args:
            path: 音频文件路径
            duration_ms: 音频时长（毫秒），None表示不限制
        """
        self.audio_file_path = path

        # 设置时间输入框的最大时长限制
        if duration_ms is not None:
            self.start_time_input.set_max_duration(duration_ms)
            self.end_time_input.set_max_duration(duration_ms)

    def show_preset_menu(self):
        """显示预设选择对话框"""
        from src.core.DictManage import DictManage

        dict_manage = DictManage()
        presets = dict_manage.dataAPI.get_all_marker_presets()

        if not presets:
            QMessageBox.information(self, "提示", "暂无预设，请先在预设管理器中创建预设")
            return

        # 创建预设选择对话框
        dialog = PresetSelectorDialog(
            presets=presets,
            current_preset_id=self.selected_preset_id,
            parent=self
        )

        # 设置对话框位置在预设按钮下方
        btn_pos = self.preset_btn.mapToGlobal(self.preset_btn.rect().bottomLeft())
        dialog.move(btn_pos)

        # 显示对话框
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_selected_data()
            if data:
                self.on_preset_selected(data['id'], data['color'], data['name'])

    def on_preset_selected(self, preset_id, color, name):
        """预设选择回调"""
        self.current_color = color
        self.selected_preset_id = preset_id
        self.update_color_button()

        # 自动填充注释
        self.label_input.setText(name)

    def choose_color(self):
        """打开颜色选择器"""
        initial_color = QColor(self.current_color)
        color = QColorDialog.getColor(initial_color, self, "选择标记颜色")

        if color.isValid():
            self.current_color = color.name()
            self.selected_preset_id = None  # 取消预设选择
            self.update_color_button()

    def clear_all(self):
        """清空所有输入"""
        self.start_time_input.clear()
        self.end_time_input.clear()
        self.label_input.clear()
        self.current_color = "#3498db"
        self.selected_preset_id = None
        self.update_color_button()

    def validate_and_create(self):
        """验证输入并创建标记"""
        if not self.audio_file_path:
            QMessageBox.warning(self, "错误", "未加载音频文件")
            return

        # 获取时间（毫秒）- TimeInput 已自动限制在有效范围内
        start_ms = self.start_time_input.get_milliseconds()
        end_ms = self.end_time_input.get_milliseconds()

        # 至少需要一个时间
        if start_ms is None and end_ms is None:
            QMessageBox.warning(self, "错误", "请至少输入一个时间")
            return

        # 获取注释
        label = self.label_input.text().strip()
        if not label:
            label = "未命名标记"

        # 判断标记类型
        if end_ms is None:
            # 点标记
            marker_data = {
                'type': 0,
                'time': start_ms if start_ms is not None else end_ms,
                'label': label,
                'color': self.current_color,
                'preset_id': self.selected_preset_id
            }
        else:
            # 范围标记
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
                'preset_id': self.selected_preset_id
            }

        # 保存到数据库
        try:
            from src.core.DictManage import DictManage
            dict_manage = DictManage()
            dict_manage.add_audio_marker(self.audio_file_path, marker_data)

            # 发出信号通知标记已创建
            self.marker_created.emit()

            QMessageBox.information(self, "成功", "标记创建成功")

            # 保留所有输入内容（不清空）

        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建标记失败:\n{str(e)}")
