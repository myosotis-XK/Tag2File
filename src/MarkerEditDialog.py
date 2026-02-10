from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QTextEdit, QGroupBox, QColorDialog, QButtonGroup)
from PyQt5.QtGui import QColor


def format_time(ms):
    """格式化毫秒为 mm:ss 格式"""
    from PyQt5.QtCore import QTime
    time = QTime(0, 0).addMSecs(ms)
    return time.toString("mm:ss")


class MarkerEditDialog(QDialog):
    """标记编辑对话框"""

    def __init__(self, marker_data=None, presets=None, parent=None):
        """
        初始化标记编辑对话框

        :param marker_data: 现有标记数据字典 {'type', 'time'/'start'/'end', 'label', 'color', 'preset_id'}
                           或 None（新建标记）
        :param presets: 预设列表 [(id, name, color, emoji, order_index, is_builtin), ...]
        :param parent: 父窗口
        """
        super().__init__(parent)
        self.marker_data = marker_data or {}
        self.presets = presets or []
        self.current_color = self.marker_data.get('color', '#3498db')
        self.selected_preset_id = self.marker_data.get('preset_id')

        self.setWindowTitle("编辑标记" if marker_data else "创建标记")
        self.resize(450, 400)

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

            for preset_id, name, color, emoji, order_index, is_builtin in self.presets:
                btn = QPushButton(f"{emoji} {name}" if emoji else name)
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

        # 4. 时间信息显示（仅在编辑模式显示）
        if self.marker_data:
            time_info = QLabel()
            time_info.setStyleSheet("color: #555; font-size: 12px; padding: 5px;")

            marker_type = self.marker_data.get('type', 0)
            if marker_type == 0:  # 点标记
                time_ms = self.marker_data.get('time', 0)
                time_info.setText(f"📍 时间点: {format_time(time_ms)}")
            else:  # 范围标记
                start_ms = self.marker_data.get('start', 0)
                end_ms = self.marker_data.get('end', 0)
                time_info.setText(f"📏 时间范围: {format_time(start_ms)} - {format_time(end_ms)}")

            layout.addWidget(time_info)

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

        # 自动填充注释：查找对应预设的名称和emoji
        for p_id, name, p_color, emoji, order_index, is_builtin in self.presets:
            if p_id == preset_id:
                # 每次点击预设时都自动填充注释
                preset_text = f"{emoji} {name}" if emoji else name
                self.text_edit.setPlainText(preset_text)
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

    def get_data(self):
        """
        获取用户输入的数据

        :return: {'label': str, 'color': str, 'preset_id': int or None}
        """
        return {
            'label': self.text_edit.toPlainText().strip(),
            'color': self.current_color,
            'preset_id': self.selected_preset_id
        }


if __name__ == "__main__":
    """测试代码"""
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 模拟预设数据
    test_presets = [
        (1, "精彩片段", "#e74c3c", "🔥", 0, 1),
        (2, "需要剪辑", "#f39c12", "✂️", 1, 1),
        (3, "重要对话", "#3498db", "💬", 2, 1),
        (4, "音乐高潮", "#9b59b6", "🎵", 3, 1),
        (5, "待优化", "#95a5a6", "⚠️", 4, 1),
    ]

    # 测试创建标记
    dialog = MarkerEditDialog(presets=test_presets)
    if dialog.exec_() == QDialog.Accepted:
        print("用户保存的数据:", dialog.get_data())

    # 测试编辑标记
    test_marker = {
        'type': 1,
        'start': 40000,
        'end': 70000,
        'label': '副歌阶段',
        'color': '#2ecc71',
        'preset_id': 4
    }
    dialog2 = MarkerEditDialog(marker_data=test_marker, presets=test_presets)
    if dialog2.exec_() == QDialog.Accepted:
        print("用户编辑后的数据:", dialog2.get_data())

    sys.exit(app.exec_())
