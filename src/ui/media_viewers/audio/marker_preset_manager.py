# 修改 marker_preset_manager.py 以使用右键菜单方式
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                             QPushButton, QColorDialog, QMessageBox, QLabel, QLineEdit, QWidget,
                             QFormLayout, QScrollArea, QMenu, QAction)
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QColor

from src.ui.components.flow_layout import QFlowLayout
from src.ui.components.style_utils import (
    apply_color_preview_button_style,
    create_colored_label,
    create_context_menu,
)


class PresetEditDialog(QDialog):
    """预设编辑对话框 - 统一的创建/编辑界面"""

    def __init__(self, preset_data=None, parent=None):
        """
        初始化预设编辑对话框

        Args:
            preset_data: 编辑时传入预设数据，新建时为 None
            parent: 父窗口
        """
        super().__init__(parent)

        self.preset_data = preset_data
        self.selected_color = preset_data.get('color', '#3498db') if preset_data else '#3498db'

        self.setWindowTitle("编辑预设" if preset_data else "添加预设")
        self.setMinimumWidth(400)

        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 表单布局
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # 预设名称
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例如：精彩片段")
        if self.preset_data:
            self.name_input.setText(self.preset_data.get('name', ''))
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
        """)
        form_layout.addRow("名称:", self.name_input)

        # 颜色选择
        color_layout = QHBoxLayout()

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(80, 35)
        self.update_color_button()
        self.color_btn.clicked.connect(self.choose_color)
        color_layout.addWidget(self.color_btn)

        color_label = QLabel("点击选择颜色")
        color_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        color_layout.addWidget(color_label)
        color_layout.addStretch()

        form_layout.addRow("颜色:", color_layout)

        layout.addLayout(form_layout)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumSize(100, 35)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        # 确认按钮
        confirm_btn = QPushButton("确定")
        confirm_btn.setMinimumSize(100, 35)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        confirm_btn.clicked.connect(self.accept_data)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)

    def update_color_button(self):
        """更新颜色按钮显示"""
        apply_color_preview_button_style(self.color_btn, self.selected_color)

    def choose_color(self):
        """打开颜色选择器"""
        initial_color = QColor(self.selected_color)
        color = QColorDialog.getColor(initial_color, self, "选择预设颜色")

        if color.isValid():
            self.selected_color = color.name()
            self.update_color_button()

    def accept_data(self):
        """验证并接受数据"""
        name = self.name_input.text().strip()

        if not name:
            QMessageBox.warning(self, "提示", "请输入预设名称")
            self.name_input.setFocus()
            return

        self.accept()

    def get_data(self):
        """获取对话框数据"""
        return {
            'name': self.name_input.text().strip(),
            'color': self.selected_color
        }


class PresetListItemWidget(QWidget):
    """预设列表项组件 - 与标签系统统一的样式"""

    def __init__(self, preset_data, parent=None):
        """
        初始化列表项组件

        Args:
            preset_data: 预设数据 {'id', 'name', 'color'}
        """
        super().__init__(parent)

        self.preset_data = preset_data

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 减少边距，让样式更接近标签
        layout.setSpacing(0)

        # 预设按钮（与标签样式一致）
        self.preset_label = create_colored_label(preset_data['name'], preset_data['color'])

        # 启用右键菜单
        self.preset_label.setContextMenuPolicy(Qt.CustomContextMenu)
        self.preset_label.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.preset_label, 1)

    def show_context_menu(self, pos):
        """显示右键菜单"""
        menu = create_context_menu(self)
        
        # 编辑动作
        edit_action = QAction("编辑", self)
        edit_action.triggered.connect(self.edit_preset)
        menu.addAction(edit_action)
        
        # 删除动作
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(self.delete_preset)
        menu.addAction(delete_action)
        
        # 获取按钮的全局位置
        btn_global_pos = self.preset_label.mapToGlobal(QPoint(0, 0))
        global_pos = btn_global_pos + pos
        menu.exec_(global_pos)

    def edit_preset(self):
        """编辑预设"""
        parent = self.parent()
        while parent and not hasattr(parent, 'edit_preset_by_data'):
            parent = parent.parent()
        if parent:
            parent.edit_preset_by_data(self.preset_data)

    def delete_preset(self):
        """删除预设"""
        parent = self.parent()
        while parent and not hasattr(parent, 'delete_preset_by_data'):
            parent = parent.parent()
        if parent:
            parent.delete_preset_by_data(self.preset_data)


class MarkerPresetManager(QDialog):
    """标记预设管理对话框 - 使用流式布局和右键菜单"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("标记预设管理")
        self.resize(400, 300)

        from src.core.DictManage import DictManage
        self.dict_manage = DictManage()
        self.dict_manage.markerPresetsChanged.connect(self.load_presets)

        self.init_ui()
        self.load_presets()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 标题说明
        title_label = QLabel("📋 管理标记预设类型")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title_label)

        # 预设显示区域 - 使用滚动区域和流式布局
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
            }
        """)

        # 创建包含流式布局的容器
        self.content_widget = QWidget()
        self.preset_layout = QFlowLayout(self.content_widget)
        self.preset_layout.setSpacing(10)
        self.preset_layout.setContentsMargins(10, 10, 10, 10)

        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area, 1)  # 给予拉伸因子

        # 按钮区域
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("➕ 添加预设")
        self.add_btn.setMinimumHeight(35)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        self.add_btn.clicked.connect(self.add_preset)
        btn_layout.addWidget(self.add_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setMinimumHeight(35)
        close_btn.setMinimumWidth(100)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def load_presets(self):
        """加载所有预设并显示在流式布局中"""
        # 清空现有组件
        self.clear_preset_widgets()

        presets = self.dict_manage.get_all_marker_presets()

        # 为每个预设创建组件
        for preset_id, name, color, order_index in presets:
            preset_data = {
                'id': preset_id,
                'name': name,
                'color': color,
                'order_index': order_index
            }

            # 创建预设组件
            preset_widget = PresetListItemWidget(preset_data)

            self.preset_layout.addWidget(preset_widget)

    def clear_preset_widgets(self):
        """清空预设组件"""
        while self.preset_layout.count():
            child = self.preset_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def add_preset(self):
        """添加新预设"""
        dialog = PresetEditDialog(parent=self)

        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()

            try:
                # 添加到数据库
                self.dict_manage.create_marker_preset(
                    data['name'],
                    data['color']
                )

                QMessageBox.information(self, "成功", f"预设 '{data['name']}' 已添加")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"添加预设失败:\n{str(e)}")

    def edit_preset_by_data(self, preset_data):
        """根据预设数据编辑"""
        self._edit_preset_data(preset_data)

    def edit_preset(self):
        """编辑选中的预设 - 保留旧方法用于兼容性"""
        # 由于现在使用流式布局，没有选中项的概念，所以不实现此方法
        pass

    def _edit_preset_data(self, preset_data):
        """执行编辑预设操作"""
        dialog = PresetEditDialog(preset_data=preset_data, parent=self)

        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()

            try:
                # 更新数据库
                self.dict_manage.update_marker_preset(
                    preset_data['id'],
                    data['name'],
                    data['color']
                )

                QMessageBox.information(self, "成功", f"预设 '{data['name']}' 已更新")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"更新预设失败:\n{str(e)}")

    def delete_preset_by_data(self, preset_data):
        """根据预设数据删除"""
        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除预设 '{preset_data['name']}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        self._delete_preset_by_data(preset_data)

    def delete_preset(self):
        """删除选中的预设 - 保留旧方法用于兼容性"""
        # 由于现在使用流式布局，没有选中项的概念，所以不实现此方法
        pass

    def _delete_preset_by_data(self, preset_data):
        """执行删除预设操作"""
        try:
            # 从数据库删除
            self.dict_manage.delete_marker_preset(preset_data['id'])

            QMessageBox.information(self, "成功", "预设已删除")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除预设失败:\n{str(e)}")

    def on_order_changed(self):
        """拖动排序后更新数据库 - 不再需要"""
        # 由于不再使用列表控件，此方法不再适用
        pass
