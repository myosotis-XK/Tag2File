from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton
from PyQt5.QtCore import Qt
from .preset_selector import PresetSelector


class PresetSelectorDialog(QDialog):
    """预设选择对话框"""

    def __init__(self, presets=None, current_preset_id=None, parent=None):
        """
        初始化预设选择对话框

        Args:
            presets: 预设列表 [(id, name, color, order_index), ...]
            current_preset_id: 当前选中的预设ID
            parent: 父窗口
        """
        super().__init__(parent)

        self.selected_preset_id = current_preset_id
        self.selected_color = None
        self.selected_name = None

        self.setWindowTitle("选择预设类型")
        self.setModal(True)
        self.setMinimumWidth(270)

        # 设置窗口标志：无边框对话框
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)

        self.init_ui(presets)

    def init_ui(self, presets):
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

    def _on_preset_selected_and_close(self, preset_id, color, name):
        """预设选中后立即关闭对话框"""
        self.selected_preset_id = preset_id
        self.selected_color = color
        self.selected_name = name

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
            pass

    def on_preset_selected(self, preset_id, color, name):
        """预设选中回调"""
        self.selected_preset_id = preset_id
        self.selected_color = color
        self.selected_name = name

    def on_selection_cleared(self):
        """选中清除回调"""
        self.selected_preset_id = None
        self.selected_color = None
        self.selected_name = None

    def get_selected_data(self):
        """
        获取选中的预设数据

        Returns:
            dict or None: {'id': int, 'color': str, 'name': str} 或 None（未选中）
        """
        if self.selected_preset_id is None:
            return None

        return {
            'id': self.selected_preset_id,
            'color': self.selected_color,
            'name': self.selected_name
        }