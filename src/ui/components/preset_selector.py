from PyQt5.QtWidgets import QWidget, QHBoxLayout, QGroupBox, QScrollArea
from PyQt5.QtCore import pyqtSignal, Qt

from .flow_layout import QFlowLayout
from src.ui.components.style_utils import create_colored_label


class PresetSelector(QWidget):
    """预设选择器组件"""

    # 信号：当预设被选中时发出 (preset_id, color, name)
    preset_selected = pyqtSignal(int, str, str)
    def __init__(self, title="预设类型", parent=None):
        """
        初始化预设选择器

        Args:
            title: GroupBox标题
            parent: 父组件
        """
        super().__init__(parent)

        self.presets = []
        self.preset_labels = []

        # 创建UI
        self.group_box = QGroupBox(title)
        
        # 使用滚动区域和流式布局
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: white;")
        
        self.flow_widget = QWidget()
        self.preset_layout = QFlowLayout(self.flow_widget)  # 使用 QFlowLayout
        self.preset_layout.setSpacing(10)
        self.preset_layout.setContentsMargins(10, 10, 10, 10)

        self.scroll_area.setWidget(self.flow_widget)
        
        # 将滚动区域添加到 GroupBox
        group_layout = QHBoxLayout()
        group_layout.addWidget(self.scroll_area)
        self.group_box.setLayout(group_layout)

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
            label = create_colored_label(name, color)

            label.preset_id = preset_id
            label.preset_color = color
            label.preset_name = name

            label.mousePressEvent = lambda event, lbl=label: self._on_label_clicked(lbl) if event.button() == Qt.LeftButton else None
            
            self.preset_layout.addWidget(label)
            self.preset_labels.append(label)

    def clear_presets(self):
        """清空所有预设按钮"""
        for label in self.preset_labels:
            self.preset_layout.removeWidget(label)
            label.deleteLater()

        self.preset_labels.clear()
        self.presets.clear()

    def _on_label_clicked(self, label):
        """预设标签点击回调"""
        self.preset_selected.emit(label.preset_id, label.preset_color, label.preset_name)
