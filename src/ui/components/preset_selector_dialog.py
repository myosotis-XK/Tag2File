"""
PresetSelectorDialog - 预设选择对话框

弹出式对话框，显示 PresetSelector 组件供用户选择预设
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton
from PyQt5.QtCore import Qt
from .preset_selector import PresetSelector


class PresetSelectorDialog(QDialog):
    """预设选择对话框"""

    def __init__(self, presets=None, current_preset_id=None, parent=None):
        """
        初始化预设选择对话框

        Args:
            presets: 预设列表 [(id, name, color, emoji, order_index, is_builtin), ...]
            current_preset_id: 当前选中的预设ID
            parent: 父窗口
        """
        super().__init__(parent)

        self.selected_preset_id = current_preset_id
        self.selected_color = None
        self.selected_name = None
        self.selected_emoji = None

        self.setWindowTitle("选择预设类型")
        self.setModal(True)
        self.setMinimumWidth(500)

        # 设置窗口标志：无边框对话框
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)

        self.init_ui(presets, current_preset_id)

    def init_ui(self, presets, current_preset_id):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        # 设置整体样式
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
        """)

        # 创建预设选择器（不显示GroupBox边框）
        self.preset_selector = PresetSelector(title="")

        # 移除 GroupBox 的边框和背景
        self.preset_selector.group_box.setStyleSheet("""
            QGroupBox {
                background-color: transparent;
                border: none;
                padding: 0;
                margin: 0;
            }
        """)

        if presets:
            self.preset_selector.load_presets(presets)

        # 如果有当前选中的预设，设置为选中状态
        if current_preset_id is not None:
            self.preset_selector.set_selected_preset(current_preset_id)

        # 连接信号 - 点击预设后立即关闭并接受
        self.preset_selector.preset_selected.connect(self._on_preset_selected_and_close)

        layout.addWidget(self.preset_selector)

        # 添加"管理预设"按钮
        self.manage_presets_btn = QPushButton("⚙️ 管理预设")
        self.manage_presets_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 8px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:pressed {
                background-color: #6c7a7b;
            }
        """)
        self.manage_presets_btn.clicked.connect(self._on_manage_presets_clicked)
        layout.addWidget(self.manage_presets_btn)

    def _on_preset_selected_and_close(self, preset_id, color, name, emoji):
        """预设选中后立即关闭对话框"""
        self.selected_preset_id = preset_id
        self.selected_color = color
        self.selected_name = name
        self.selected_emoji = emoji

        # 立即接受并关闭
        self.accept()

    def _on_manage_presets_clicked(self):
        """打开预设管理器"""
        from ..media_viewers.audio.marker_preset_manager import MarkerPresetManager

        # 关闭当前对话框
        self.close()

        # 打开预设管理器
        manager = MarkerPresetManager(self.parent())
        if manager.exec_():
            # 如果预设管理器关闭后，可以选择重新打开预设选择对话框
            # 这里暂时不实现，让用户手动再次点击预设按钮
            pass

    def on_preset_selected(self, preset_id, color, name, emoji):
        """预设选中回调"""
        self.selected_preset_id = preset_id
        self.selected_color = color
        self.selected_name = name
        self.selected_emoji = emoji

    def on_selection_cleared(self):
        """选中清除回调"""
        self.selected_preset_id = None
        self.selected_color = None
        self.selected_name = None
        self.selected_emoji = None

    def get_selected_data(self):
        """
        获取选中的预设数据

        Returns:
            dict or None: {'id': int, 'color': str, 'name': str, 'emoji': str} 或 None（未选中）
        """
        if self.selected_preset_id is None:
            return None

        return {
            'id': self.selected_preset_id,
            'color': self.selected_color,
            'name': self.selected_name,
            'emoji': self.selected_emoji
        }


if __name__ == "__main__":
    """测试代码"""
    import sys
    from PyQt5.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout

    app = QApplication(sys.argv)

    # 测试窗口
    window = QWidget()
    window.setWindowTitle("PresetSelectorDialog 测试")
    window.resize(400, 200)

    layout = QVBoxLayout(window)

    # 模拟预设数据
    test_presets = [
        (1, "精彩片段", "#e74c3c", "🔥", 0, 1),
        (2, "需要剪辑", "#f39c12", "✂️", 1, 1),
        (3, "重要对话", "#3498db", "💬", 2, 1),
        (4, "音乐高潮", "#9b59b6", "🎵", 3, 1),
        (5, "待优化", "#95a5a6", "⚠️", 4, 1),
    ]

    # 测试按钮
    test_btn = QPushButton("打开预设选择对话框")
    test_btn.setMinimumHeight(40)

    def open_dialog():
        dialog = PresetSelectorDialog(presets=test_presets, current_preset_id=2, parent=window)

        # 设置对话框位置在按钮下方
        btn_pos = test_btn.mapToGlobal(test_btn.rect().bottomLeft())
        dialog.move(btn_pos)

        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_selected_data()
            if data:
                print(f"选中预设: {data['emoji']} {data['name']} (颜色: {data['color']})")
                test_btn.setText(f"{data['emoji']} {data['name']}")
                test_btn.setStyleSheet(f"background-color: {data['color']}; color: white;")
            else:
                print("未选择预设")
        else:
            print("用户取消")

    test_btn.clicked.connect(open_dialog)

    layout.addWidget(test_btn)
    layout.addStretch()

    window.show()
    sys.exit(app.exec_())
