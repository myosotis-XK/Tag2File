"""
PresetSelector 组件 - 预设类型选择器

功能特性：
- 水平排列的可选预设按钮
- 支持预设颜色显示和emoji
- 单选模式（QButtonGroup）
- 提供选中回调信号
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QGroupBox, QPushButton, QButtonGroup
from PyQt5.QtCore import pyqtSignal


class PresetSelector(QWidget):
    """预设选择器组件"""

    # 信号：当预设被选中时发出 (preset_id, color, name, emoji)
    preset_selected = pyqtSignal(int, str, str, str)
    # 信号：当取消选中时发出
    selection_cleared = pyqtSignal()

    def __init__(self, title="预设类型", parent=None):
        """
        初始化预设选择器

        Args:
            title: GroupBox标题
            parent: 父组件
        """
        super().__init__(parent)

        self.presets = []
        self.preset_buttons = []
        self.selected_preset_id = None

        # 创建UI
        self.group_box = QGroupBox(title)
        self.preset_layout = QHBoxLayout()
        self.preset_layout.setSpacing(10)
        self.preset_layout.setContentsMargins(10, 10, 10, 10)

        self.preset_button_group = QButtonGroup(self)
        self.preset_button_group.setExclusive(True)

        self.group_box.setLayout(self.preset_layout)

        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.group_box)

    def load_presets(self, presets):
        """
        加载预设列表

        Args:
            presets: 预设列表 [(id, name, color, emoji, order_index, is_builtin), ...]
        """
        # 清空现有按钮
        self.clear_presets()

        self.presets = presets

        if not presets:
            return

        # 创建预设按钮
        for preset_id, name, color, emoji, order_index, is_builtin in presets:
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
            btn.setProperty('preset_name', name)
            btn.setProperty('preset_emoji', emoji or "")

            # 连接点击事件
            btn.clicked.connect(
                lambda checked, pid=preset_id, c=color, n=name, e=emoji or "":
                self._on_button_clicked(checked, pid, c, n, e)
            )

            self.preset_layout.addWidget(btn)
            self.preset_button_group.addButton(btn)
            self.preset_buttons.append(btn)

    def clear_presets(self):
        """清空所有预设按钮"""
        for btn in self.preset_buttons:
            self.preset_layout.removeWidget(btn)
            self.preset_button_group.removeButton(btn)
            btn.deleteLater()

        self.preset_buttons.clear()
        self.presets.clear()
        self.selected_preset_id = None

    def _on_button_clicked(self, checked, preset_id, color, name, emoji):
        """预设按钮点击回调"""
        if checked:
            self.selected_preset_id = preset_id
            self.preset_selected.emit(preset_id, color, name, emoji)
        else:
            self.selected_preset_id = None
            self.selection_cleared.emit()

    def set_selected_preset(self, preset_id):
        """
        设置当前选中的预设

        Args:
            preset_id: 预设ID，None表示取消选中
        """
        if preset_id is None:
            # 取消所有选中
            checked_btn = self.preset_button_group.checkedButton()
            if checked_btn:
                checked_btn.setChecked(False)
            self.selected_preset_id = None
            return

        # 查找并选中对应按钮
        for btn in self.preset_buttons:
            if btn.property('preset_id') == preset_id:
                btn.setChecked(True)
                self.selected_preset_id = preset_id
                break

    def get_selected_preset_id(self):
        """
        获取当前选中的预设ID

        Returns:
            int or None: 预设ID，未选中时返回None
        """
        return self.selected_preset_id

    def clear_selection(self):
        """清除当前选中状态"""
        self.set_selected_preset(None)


if __name__ == "__main__":
    """测试代码"""
    import sys
    from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget, QLabel

    app = QApplication(sys.argv)

    # 创建测试窗口
    window = QWidget()
    window.setWindowTitle("PresetSelector 测试")
    window.resize(600, 200)

    layout = QVBoxLayout(window)

    # 创建预设选择器
    selector = PresetSelector("选择预设类型")

    # 模拟预设数据
    test_presets = [
        (1, "精彩片段", "#e74c3c", "🔥", 0, 1),
        (2, "需要剪辑", "#f39c12", "✂️", 1, 1),
        (3, "重要对话", "#3498db", "💬", 2, 1),
        (4, "音乐高潮", "#9b59b6", "🎵", 3, 1),
        (5, "待优化", "#95a5a6", "⚠️", 4, 1),
    ]

    selector.load_presets(test_presets)

    # 添加状态显示标签
    status_label = QLabel("未选择预设")
    status_label.setStyleSheet("padding: 10px; background-color: #ecf0f1; border-radius: 3px;")

    # 连接信号
    def on_preset_selected(preset_id, color, name, emoji):
        status_label.setText(f"选中预设: {emoji} {name} (ID: {preset_id}, 颜色: {color})")
        status_label.setStyleSheet(f"padding: 10px; background-color: {color}; color: white; border-radius: 3px;")

    def on_selection_cleared():
        status_label.setText("未选择预设")
        status_label.setStyleSheet("padding: 10px; background-color: #ecf0f1; border-radius: 3px;")

    selector.preset_selected.connect(on_preset_selected)
    selector.selection_cleared.connect(on_selection_cleared)

    # 添加到布局
    layout.addWidget(selector)
    layout.addWidget(status_label)
    layout.addStretch()

    window.show()
    sys.exit(app.exec_())
