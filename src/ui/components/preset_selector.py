"""
PresetSelector 组件 - 预设类型选择器

功能特性：
- 水平排列的可选预设按钮
- 支持预设颜色显示
- 单选模式（QButtonGroup）
- 提供选中回调信号
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QGroupBox, QPushButton, QButtonGroup
from PyQt5.QtCore import pyqtSignal


class PresetSelector(QWidget):
    """预设选择器组件"""

    # 信号：当预设被选中时发出 (preset_id, color, name)
    preset_selected = pyqtSignal(int, str, str)
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
            presets: 预设列表 [(id, name, color, order_index), ...]
        """
        # 清空现有按钮
        self.clear_presets()

        self.presets = presets

        if not presets:
            return

        # 创建预设按钮
        for preset_id, name, color, order_index in presets:
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
            btn.setProperty('preset_name', name)

            # 连接点击事件
            btn.clicked.connect(
                lambda checked, pid=preset_id, c=color, n=name:
                self._on_button_clicked(checked, pid, c, n)
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

    def _on_button_clicked(self, checked, preset_id, color, name):
        """预设按钮点击回调"""
        if checked:
            self.selected_preset_id = preset_id
            self.preset_selected.emit(preset_id, color, name)
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